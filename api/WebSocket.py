# =============================================================================
# api/WebSocket.py —— WebSocket 端点（长连接入口，整个聊天室的"门口"）
# =============================================================================
# 【WebSocket 和普通 HTTP 的区别】
#   HTTP：一问一答，说完就断。服务器不能主动给你发消息。
#   WebSocket：一次握手，之后连接一直开着，双方随时都能发消息。
#              → 聊天室、在线协作、实时推送都靠它。
#
# 【WebSocketEndpoint 的三个生命周期方法】
#   继承 starlette 的 WebSocketEndpoint 后，只要实现这三个方法：
#     on_connect   : 有人连进来时（握手完成）
#     on_receive   : 收到一条消息时
#     on_disconnect: 断开时
#   相当于给你一个"专门处理长连接"的模板，省得手写 while 循环收消息。
#
# 【★ 握手鉴权为什么要把 token 放 URL 里】
#   浏览器的原生 WebSocket API（new WebSocket(url)）**不支持自定义请求头**，
#   所以没法像 HTTP 那样带 Authorization 头。
#   只能退而求其次：把 token 拼在 URL 上 → 服务端从 query_params 里取。
#   这是一个真实的浏览器限制，面试问到可以说清楚。
#
# 【它在链路里的位置】
#   浏览器 new WebSocket("/api/v1/room/socketws?token=xxx")
#     → on_connect：验 token → 创建 OnlineUser → 加入在线表 → 发布"有人上线"
#     → on_receive：把消息丢给 Redis 发布
#     → RoomConnectionManager 的后台循环收到 Redis 消息 → 广播给所有人
#     → on_disconnect：移出在线表 → 发布"有人下线"
# =============================================================================
from typing import Optional, Any

from fastapi import APIRouter

from starlette.endpoints import WebSocketEndpoint
from starlette.websockets import WebSocket
from starlette.responses import FileResponse
from fastapi import status

from utils.auth import AuthTokenHelper

router_char = APIRouter(tags=["聊天室"])

# 从独立文件拿 OnlineUser，避免和 RoomConnectionManager 互相 import（循环导入）
from models.OnlineUser import OnlineUser

from RoomConnectionManager import RoomConnectionManager

# ★ 全局唯一的连接管理器实例。
#   所有 WebSocket 连接都登记在它内部的字典里，
#   所以它必须是模块级唯一的（不能每个请求 new 一个，否则各自管各自的，看不到别人）。
room_manager = RoomConnectionManager()


@router_char.websocket_route("/api/v1/room/socketws")
class ChatRoomWebSocket(WebSocketEndpoint):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 每个连接一个实例，所以当前用户存在实例属性上是安全的
        self.curr_user: Optional[OnlineUser] = None

    # ---- 握手 + 鉴权 --------------------------------------------------------
    async def curr_user_login_init(self, websocket: WebSocket):
        await websocket.accept()                       # 接受连接，握手完成
        token = websocket.query_params.get("token")    # ★ 只能从 query 参数拿（不能读请求头）

        if not token:
            # 没带 token → 用标准状态码 1008（策略违规）主动关掉
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="未提供token")
            raise RuntimeError("用户还没有登录！")

        if not self.curr_user and token:
            # 解析 JWT，拿到签发时写进去的 phone_number / username
            payload = AuthTokenHelper.token_decode(token)
            phone_number = payload.get("phone_number")
            username = payload.get("username")
            # 造一个 OnlineUser，把"活的连接"一起装进去
            self.curr_user = OnlineUser(username=username, phone_number=phone_number, WebSocket=websocket)

            # 单点登录：同一个人已经在房间里了，就不让第二次连
            if room_manager.check_user_logic(self.curr_user):
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="用户已登录")
                raise RuntimeError("用户已登录！")

    async def check_user_in_logic(self):
        # 预留的检查方法（目前是空实现，占位用）
        if self.curr_user:
            pass

    # ---- ① 连接建立 ---------------------------------------------------------
    async def on_connect(self, WebSocket):
        await self.curr_user_login_init(WebSocket)
        # 加进"在线表"（内存里的字典）
        room_manager.user_add_login_room(self.curr_user)
        # 通过 Redis 发布"有人上线" → 后台循环会广播给所有人
        await room_manager.publish_user_login(self.curr_user)

    # ---- ② 收到消息 ---------------------------------------------------------
    async def on_receive(self, websocket: WebSocket, msg: str) -> None:
        if self.curr_user is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="用户未登录")
            raise RuntimeError("用户未登录！")
        # 只接受文本消息（1003 = 不支持的数据类型）
        if not isinstance(msg, str):
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA, reason="消息格式错误")
            raise RuntimeError("消息格式错误！")
        # ★ 关键：这里不是直接广播，而是"发布到 Redis"
        #   为什么要绕一层？因为将来起多个进程时，只有经过 Redis
        #   才能让 A 进程的用户看到 B 进程用户发的消息。
        await room_manager.publish_user_send_message(self.curr_user, msg)

    # ---- ③ 连接断开 ---------------------------------------------------------
    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        # 从在线表移除
        room_manager.user_out_logout_room(self.curr_user)
        # 发布"有人下线" → 广播通知其他人 + 刷新在线名单
        await room_manager.publish_user_logout(self.curr_user)
        del self.curr_user


# 聊天室页面（返回静态 HTML，前端在里面 new WebSocket）
@router_char.get("/api/v1/room/online")
async def websocket_endpoint():
    return FileResponse("chat_room.html")