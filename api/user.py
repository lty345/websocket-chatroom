# =============================================================================
# api/user.py —— 用户注册 / 登录接口（HTTP 部分）
# =============================================================================
# 【它在链路里的位置】
#   前端页面（user_register.html / user_login.html）
#     → 这里的接口
#     → servies/UserServeries.py（查库/写库）
#     → 登录成功后签发 JWT，跳转到聊天室页面（token 放在 URL 里带过去）
#
# 【四个接口】
#   GET /register        返回注册页面（HTML）
#   GET /register_action 真正执行注册
#   GET /login           返回登录页面（HTML）
#   GET /login_action    真正执行登录，成功则 302 跳到聊天室
#
# 【★ 两个真实问题，复习时记住】
#   1) 注册/登录用的是 GET 而不是 POST
#      → 密码会出现在 URL 里，进而进入浏览器历史、服务器访问日志、代理日志。
#      正确做法：@router_user.post(...) + 用 JSON body 传参。
#   2) 登录成功后把 token 拼在跳转 URL 上（?token=xxx）
#      → 同样会留在浏览器历史里。更安全的做法是 Set-Cookie（httpOnly）或
#        前端拿到 token 后存内存/localStorage。
#   但 WebSocket 握手拿不到自定义头，所以前端页面用 query 参数取 token 是可以理解的权衡。
# =============================================================================
import datetime

from fastapi import FastAPI, APIRouter
from fastapi import Depends
from starlette.responses import FileResponse, RedirectResponse

from schemas.LoginAaction import LoginAaction
from schemas.RegisterAaction import RegisterAction
from dependencies.dependencies import get_db_session
from sqlalchemy.ext.asyncio import AsyncSession

from servies import UserServeries
from utils.auth import AuthTokenHelper

# prefix 让这组接口统一带上 /api/v1/user 前缀，tags 用于 /docs 文档分组
router_user = APIRouter(prefix="/api/v1/user", tags=["用户登录API"])


# ---- 返回注册页面（静态 HTML）------------------------------------------------
@router_user.get("/register")
async def index():
    return FileResponse("user_register.html")


# ---- 执行注册 ---------------------------------------------------------------
# Depends() 不带参数 = "把同名查询参数按 schema 收进来"（GET 传参）
@router_user.get("/register_action")
async def register(user: RegisterAction = Depends(), db_session: AsyncSession = Depends(get_db_session)):
    # 先按手机号查一遍，存在就不让注册（防重复）
    result = await UserServeries.get_user_by_phone_number(db_session, user.phone_number)
    if not result:
        # model_dump() 把 pydantic 对象转成 dict，
        # ** 展开后正好对上 create_user(**kwargs) 的入参
        await UserServeries.create_user(db_session=db_session, **user.model_dump())
        return {"code": 200, "msg": "注册成功"}
    else:
        return {"code": 400, "msg": "用户已存在"}


# ---- 返回登录页面 -----------------------------------------------------------
@router_user.get("/login")
async def login():
    return FileResponse("user_login.html")


# ---- 执行登录 ---------------------------------------------------------------
@router_user.get("/login_action")
async def login_action(user: LoginAaction = Depends(), db_session: AsyncSession = Depends(get_db_session)):
    # 手机号 + 密码一起去库里比（明文比对，见 servies 的说明）
    result = await UserServeries.check_user_phone_number_and_password(
        db_session, user.phone_number, user.password
    )
    if result:
        # 校验通过 → 组装 token 内容（payload）
        data = {
            'iss': user.phone_number,          # issuer 签发者
            'sub': 'xiaozhongtongxue',         # subject 主体（这里写的是固定值，实际该写用户 id）
            'phone_number': user.phone_number, # 自定义字段，WebSocket 握手时会用到
            'username': result.username,
            # ★ 这里写的 2 天会被 utils/auth.py 里的默认 15 分钟覆盖掉（详见那边注释）
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=2)
        }
        token = AuthTokenHelper.token_encode(data=data)
        # 302 跳到聊天室页面，并把 token 通过 URL 参数带过去
        return RedirectResponse(f"http://127.0.0.1:8000/api/v1/room/online?token={token}")
    else:
        return {"code": 400, "msg": "用户名或密码错误,请重新输入"}