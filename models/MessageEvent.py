# =============================================================================
# models/MessageEvent.py —— Redis Pub/Sub 消息的结构
# =============================================================================
# 【它在链路里的位置】
#   RoomConnectionManager.do_listaction() 里：
#       message = await channel.get_message(...)     # 从 Redis 收到一条原始消息
#       message_event = MessageEvent(**message)      # ← 用它包装成对象
#       payload = json.loads(message_event.data)     # 再取内容
#
# 【为什么需要它】
#   Redis 发过来的是一条 dict（含 type/channel/data/pattern 四个键）。
#   用 dataclass 包一层，就能用 message_event.data 这种属性访问，
#   比写 message["data"] 更清晰，也让 IDE 能补全。
#
# 【四个字段的含义】
#   type    : Redis 消息类型（如 "message" 表示是普通发布消息）
#   channel : 哪个频道来的（本项目的三个频道见 RoomConnectionManager）
#   data    : 消息内容（JSON 字符串，真正的业务数据在这里）
#   pattern : 订阅模式（用通配符订阅时才有值，本项目用不到，所以默认 None）
# =============================================================================
from dataclasses import dataclass
from typing import Optional

from models.User import User


@dataclass
class MessageEvent:
    type: str
    channel: str
    data: str                    # JSON 字符串，要 json.loads 才能用
    pattern: Optional[str] = None