# =============================================================================
# schemas/RegisterAaction.py —— 注册请求的数据格式
# =============================================================================
# 【它在链路里的位置】
#   api/user.py 的 register(user: RegisterAction = Depends(), ...)
#   → FastAPI 校验 username/password/phone_number 三个字段
#   → 通过后交给 servies/UserServeries.create_user 写库
#
# 【字段和 models/User.py 一一对应】
#   username / password / phone_number
#   ★ 但这里没做任何约束（比如密码最短长度、手机号格式），
#     实际项目应该写成：
#       password: str = Field(min_length=6)
#       phone_number: str = Field(pattern=r"^1[3-9]\d{9}$")
# =============================================================================
from pydantic import BaseModel


class RegisterAction(BaseModel):
    username: str
    password: str
    phone_number: int