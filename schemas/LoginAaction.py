# =============================================================================
# schemas/LoginAaction.py —— 登录请求的数据格式
# =============================================================================
# 【schemas 和 models 的区别（重要）】
#   models/  = 数据库长什么样（表结构，SQLAlchemy）
#   schemas/ = 接口收发的数据长什么样（请求/响应格式，Pydantic）
#
# 【它在链路里的位置】
#   api/user.py 的 login_action(user: LoginAaction = Depends(), ...)
#   → FastAPI 自动从 URL 参数里取值，按这个类校验类型
#   → 校验不过会直接返回 422，进不到业务代码
#
# 【命名注意】
#   文件名是 LoginAaction（多了一个 a），类名是 LoginAaction，
#   这是笔误但被下面的 import 引用了，改名要同步改 api/user.py。
# =============================================================================
from pydantic import BaseModel


class LoginAaction(BaseModel):
    username: str
    password: str
    phone_number: int