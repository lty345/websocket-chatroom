# =============================================================================
# models/OnlineUser.py —— 内存对象："此刻在线的用户"
# =============================================================================
# 【为什么不能直接用 User】
#   User 是数据库里的一行，能存能查；
#   但"活着的 WebSocket 连接"既存不进数据库，也传不过 Redis
#   → 必须单独定义一个类来装它。
#
# 【它在链路里的位置】
#   api/WebSocket.py 握手成功后创建 OnlineUser（带 WebSocket）
#   → 交给 RoomConnectionManager 管起来
#   → 广播时遍历这些对象，调 user.WebSocket.send_json(...)
#
# 【为什么放在 models/ 目录下】
#   原作者注释说明了：放这里是为了避开
#   RoomConnectionManager 与 api.WebSocket 之间的循环导入。
#   （两个文件都要用到 OnlineUser，谁 import 谁都会绕圈，所以抽到第三个文件里）
#
# 【@dataclass 是什么】
#   自动生成 __init__、__repr__ 等样板代码。
#   写 @dataclass + 三个字段，等价于手写一个写满 __init__ 的普通类。
# =============================================================================
from dataclasses import dataclass

from starlette.websockets import WebSocket


@dataclass
class OnlineUser:
    """此刻【在线】的用户。

    注意: 这和 models/User.py 里的 User 是两个不同的概念。
        models/User.py 的 User  ->  数据库里的一行用户档案 (username/password/phone_number)
        本文件的 OnlineUser    ->  此刻连着的那个人 (带一条活的 WebSocket 连接)

    WebSocket 是活连接, 既存不进数据库, 也传不了 Redis, 所以必须单独一个类。
    放在 models/ 下是为了避开 RoomConnectionManager 与 api.WebSocket 之间的循环导入。
    """

    username: str
    phone_number: str
    WebSocket: WebSocket    # ★ 活的连接对象，这是整个实时通信的"话筒"