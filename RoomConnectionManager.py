# =============================================================================
# RoomConnectionManager.py —— 连接管理器（在线用户登记 + 消息广播核心）
# =============================================================================
# 【它到底管什么】
#   1) 一份"谁在线"的内存登记表（_users_socket 字典）
#   2) 一套广播方法：把消息发给在线表里的每一个连接
#   3) 一套 Redis 发布/订阅方法：让消息先经过 Redis，再广播
#
# 【为什么消息要绕 Redis 一圈】
#   假设只用一个进程：内存字典直接广播就够了，Redis 是多余的。
#   但如果起了多个 worker 进程（uvicorn --workers 4）：
#     A 进程的字典里只有连在 A 上的用户，B 进程看不到 A 的用户。
#   这时必须靠 Redis 做"公共广播喇叭"：
#     A 的用户发消息 → publish 到 Redis 频道 → A、B 两个进程都订阅了 → 各自广播给自己的人
#   ★ 面试被问"为什么用 Pub/Sub"，这就是标准答案。同时要诚实说：
#     单进程部署时它是冗余的，属于为将来扩容预留的设计。
#
# 【三个 Redis 频道的分工】
#   chat: system_msg_user_login   → 有人上线
#   chat: system_msg_user_logout  → 有人下线
#   chat: user_send_msg           → 有人发了聊天消息
#
# 【数据流（完整一圈）】
#   浏览器连上 → on_connect → publish_user_login
#     → Redis 频道 system_msg_user_login
#     → do_listaction 里的 reader 收到
#     → broadcast_room_user_login（通知老用户"xx 来了"）
#     → broadcast_system_room_updata_userlist（刷新所有人的在线名单）
# =============================================================================

from datetime import datetime
from typing import Dict, List, Optional

import json
import asyncio

import async_timeout
from redis.asyncio.client import PubSub, Redis
from models.OnlineUser import OnlineUser

from models.MessageEvent import MessageEvent
import redis.asyncio as aioredis


class RoomConnectionManager:
    pass    # ← 这行 pass 是多余的残留，留着不影响运行

    def __init__(self):
        # ★ 在线登记表：{手机号: OnlineUser}
        #   注意这是纯内存的，进程一重启就清空（对聊天室来说可以接受）
        self._users_socket: Dict[str, OnlineUser] = {}

        # Redis 客户端和订阅对象，延迟到 register_pubsub() 才创建
        self.redis: Optional[Redis] = None
        self.pubsub: Optional[PubSub] = None

    # =========================================================================
    # 一、在线表的增删查
    # =========================================================================
    def user_add_login_room(self, user: OnlineUser):
        # 用手机号做 key（天然唯一）。已存在就不重复加
        if user.phone_number not in self._users_socket:
            self._users_socket[user.phone_number] = user

    def user_out_logout_room(self, user: OnlineUser):
        if user.phone_number in self._users_socket:
            del self._users_socket[user.phone_number]

    def check_user_logic(self, userlogin: OnlineUser):
        # 返回 True 表示"这个人已经在房间里了" → 用于单点登录拦截
        if userlogin.phone_number in self._users_socket:
            return True
        return False

    # =========================================================================
    # 二、广播方法（真正发消息给客户端的地方）
    # =========================================================================
    # 共同套路：遍历 _users_socket，对每个人调 WebSocket.send_json(...)
    # send_json 会自动把 dict 转成 JSON 文本发出去

    async def broadcast_system_room_updata_userlist(self):
        # 把当前所有在线用户拼成 ["张三(138...)", "李四(139...)"] 这样的名单
        user_online_list = [f"{user.username}({user.phone_number})"
                            for userid, user in self._users_socket.items()]
        for userid, user in self._users_socket.items():
            await user.WebSocket.send_json(
                {
                    "type": "system_room_update_userlist",   # 前端根据 type 决定怎么渲染
                    "data": {"user_list": user_online_list}
                }
            )

    async def broadcast_room_user_login(self, curr_user: OnlineUser):
        # 通知所有人："有人上线了"
        for userid, user in self._users_socket.items():
            await user.WebSocket.send_json(
                {
                    "type": "system_msg_user_login",
                    "data": {
                        'phone_number': curr_user.phone_number,
                        'username': curr_user.username
                    }
                }
            )

    async def broadcast_room_user_logout(self, leave_user: OnlineUser):
        # 通知所有人："有人下线了"
        for userid, user in self._users_socket.items():
            await user.WebSocket.send_json(
                {
                    "type": "system_msg_user_logout",
                    "data": {
                        'phone_number': leave_user.phone_number,
                        'username': leave_user.username
                    }
                }
            )

    async def broadcast_user_send_message(self, leave_user: OnlineUser, msg: str):
        # 把聊天内容发给所有人。
        # ★ 小技巧：给发送者自己显示"我(张三)说:..."，给别人显示"张三说:..."
        for userid, user in self._users_socket.items():
            if userid == leave_user.phone_number:
                sendmsg = f"我({leave_user.username})说:{msg}"
            else:
                sendmsg = f"{leave_user.username}说:{msg}"
            await user.WebSocket.send_json(
                {
                    "type": "user_send_message",
                    "data": {
                        'phone_number': leave_user.phone_number,
                        'username': leave_user.username,
                        'message': sendmsg,
                        'datetime': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                }
            )

    # =========================================================================
    # 三、Redis 连接与订阅
    # =========================================================================
    async def register_pubsub(self):
        # 懒连接：第一次用才建 Redis 客户端（main.py 的 lifespan 里调一次）
        if not self.redis:
            # decode_responses=True 让返回的是 str 而不是 bytes，省得手动解码
            self.redis: Redis = aioredis.from_url(
                "redis://localhost", encoding="utf-8", decode_responses=True
            )
            self.pubsub: PubSub = self.redis.pubsub()

    async def do_listaction(self):
        """订阅三个频道，并启动一个后台循环持续处理收到的消息。"""

        await self.pubsub.subscribe(
            "chat: system_msg_user_login",
            "chat: system_msg_user_logout",
            "chat: user_send_msg"
        )

        async def reader(channel: aioredis.client.PubSub):
            # ★ 这个循环就是"消息中转站"：Redis 有新消息 → 取出 → 广播给客户端
            while True:
                try:
                    # async_timeout.timeout(1) 表示"最多等 1 秒"
                    # 等不到就抛 TimeoutError，被下面的 except 吃掉，继续下一轮
                    async with async_timeout.timeout(1):
                        message = await channel.get_message(ignore_subscribe_messages=True)
                        if message is not None:
                            # 原始 message 是 dict，包装成 MessageEvent 方便属性访问
                            message_event = MessageEvent(**message)
                            payload = json.loads(message_event.data)
                            d = payload["user"]

                            # ★ 注意这里 WebSocket=None：
                            #   Redis 里传的只是"谁上线了"这个事实，
                            #   活的连接对象只在本进程内存里，过不了 Redis。
                            u = OnlineUser(username=d["username"], phone_number=d["phone_number"], WebSocket=None)

                            if message_event.channel == 'chat: system_msg_user_login':
                                await self.broadcast_system_room_updata_userlist()
                                await self.broadcast_room_user_login(curr_user=u)

                            if message_event.channel == 'chat: system_msg_user_logout':
                                await self.broadcast_room_user_logout(leave_user=u)
                                await self.broadcast_system_room_updata_userlist()

                            if message_event.channel == 'chat: user_send_msg':
                                await self.broadcast_user_send_message(leave_user=u, msg=payload['msg'])

                        # ★ 这里有个真实的性能问题：
                        #   用「每秒轮询 get_message」而不是「阻塞式 listen」，
                        #   导致消息最多延迟 1 秒才广播出去。
                        #   更好的写法是：
                        #       async for message in self.pubsub.listen(): ...
                        #   它是阻塞等待，一有消息立刻处理，没有轮询延迟。
                        #   而且下面 finally 外面还有一句 sleep(1)，等于双倍等待。
                        await asyncio.sleep(1)
                except asyncio.TimeoutError:
                    pass                      # 1 秒内没消息，正常情况，忽略
                except Exception as e:
                    print("reader 出错:", e)   # 兜底：单条消息处理失败不要让整个循环挂掉
                await asyncio.sleep(1)         # ← 又睡 1 秒（重复的，可以删掉一个）

        # create_task = 把这个循环扔到后台跑，不阻塞当前流程
        # （否则 await reader() 会让 register_pubsub 永远不返回，服务起不来）
        asyncio.create_task(reader(self.pubsub))

    # =========================================================================
    # 四、Redis 发布方法（把事件丢进频道，等着 reader 收到后广播）
    # =========================================================================
    async def publish_user_send_message(self, user: OnlineUser, msg: str):
        # 发布一条聊天消息。注意传的是"用户身份 + 消息内容"，不带连接对象
        await self.redis.publish("chat: user_send_msg", json.dumps({
            "user": {"username": user.username, "phone_number": user.phone_number},
            "msg": msg
        }))

    async def publish_user_login(self, user: OnlineUser):
        await self.redis.publish("chat: system_msg_user_login",
                                 json.dumps({"user": {"username": user.username,
                                                      "phone_number": user.phone_number}}))

    async def publish_user_logout(self, user: OnlineUser):
        await self.redis.publish("chat: system_msg_user_logout",
                                 json.dumps({"user": {"username": user.username,
                                                      "phone_number": user.phone_number}}))