# =============================================================================
# servies/UserServeries.py —— 用户相关的数据库操作（服务层）
# =============================================================================
# 【目录名 servies 是拼错了】原本应该是 services。已经被多处 import 引用，
#   改名要全局替换。复习时知道这是"业务逻辑层"就行。
#
# 【它在链路里的位置】
#   api/user.py（接口层，只管收请求、返响应）
#      → servies/UserServeries.py（业务层，管"怎么查/怎么写库"）
#         → models/User.py（表结构）
#
#   为什么要分两层？接口层不该写 SQL，业务层不该关心 HTTP。
#   这样换个接口（比如再加个"微信登录"）能复用同一套业务逻辑。
#
# 【三个函数的分工】
#   get_user_by_phone_number         : 查有没有这个手机号（注册时判重）
#   create_user                      : 插入一条用户
#   check_user_phone_number_and_password : 登录校验
# =============================================================================

from fastapi import Depends
from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from models.User import User
from dependencies.dependencies import get_db_session


# 【参数默认值写成 Depends(...) 在这里其实没用】
#   Depends() 只在**路由函数**的参数上才会被 FastAPI 解析。
#   这里是普通函数，默认值就是 Depends 对象本身 ——
#   好在所有调用方都显式传了 db_session，所以没出问题。
#   标准写法是直接 db_session: AsyncSession（不给默认值）。
# ★ 注意下面这行的写法：phone_number=str 里的 =str 是"默认值"，不是类型标注。
#   这是教材里的怪写法（把类型对象当默认值用）。如果想规范成 phone_number: str，
#   必须同时给它一个默认值（phone_number: str = None），否则会报
#   "parameter without a default follows parameter with a default" 语法错误。
async def get_user_by_phone_number(db_session: AsyncSession = Depends(get_db_session()), phone_number: str = str):
    # select(User).where(...) 是 SQLAlchemy 2.x 的新写法（老版本是 User.query.filter_by）
    se = select(User).where(User.phone_number == phone_number)
    result = await db_session.execute(se)      # ★ 异步会话必须 await
    return result.scalars().first()            # scalars() 把行对象拆出来，first() 取第一条或 None


async def create_user(db_session: AsyncSession, **kwargs):
    # 用 **kwargs 接参数，好处是调用方传什么字段都行（api 层直接 model_dump() 展开）
    user = User(
        username=kwargs.get("username"),
        password=kwargs.get("password"),      # ★ 明文直接入库，见 models/User.py 的说明
        phone_number=kwargs.get("phone_number")
    )
    db_session.add(user)                       # 加进会话（此时还没落库）
    await db_session.commit()                  # ★ 提交才真正写入数据库
    await db_session.refresh(user)             # 从库里读回（拿到自增 id 等数据库生成的值）
    return user


# ★ 这一行必须写成单行：三个参数都得有默认值（Depends(...) / int / str），
#   如果把参数拆成多行、把 phone_number/password 挪到无默认值的位置，
#   Python 会报 "parameter without a default follows parameter with a default"。
async def check_user_phone_number_and_password(db_session: AsyncSession = Depends(get_db_session()), phone_number: int = int, password: str = str):
    # 把"手机号 + 密码"两个条件一起放进 where，查得到就说明匹配。
    # ★ 这也是明文比对的证据：如果密码是 bcrypt 哈希，就不可能这样直接比对，
    #   必须先把明文密码用 verify_password() 去校验哈希。
    response = await db_session.execute(
        select(User).where(User.phone_number == phone_number, User.password == password)
    )
    return response.scalars().first()