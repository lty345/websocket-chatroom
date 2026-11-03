# =============================================================================
# dependencies/dependencies.py —— 依赖注入：每个请求一个数据库会话
# =============================================================================
# 【它在链路里的位置】
#   路由函数的参数写 db_session: AsyncSession = Depends(get_db_session)，
#   FastAPI 看到 Depends 就自动调这个生成器，把 yield 出来的会话注入进去。
#
# 【为什么用 yield（生成器）而不是直接 return】
#   这样才能表达"用完要收拾"：
#     请求进来 → 执行到 yield → 把会话交给路由函数
#     路由函数跑完（或抛异常）→ 回到这里执行 finally
#   → 自动 close()，不会漏连接。
#
# 【和预约挂号项目里的区别】
#   这边只做了 close，没有自动 commit/rollback
#   → 所以业务代码（servies/*）里必须自己 await db_session.commit()。
#   预约挂号那份做了自动提交/回滚，更完善，两种写法都可以。
# =============================================================================
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from db.database import SessionLocal


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    db_session = None
    try:
        # 创建一个会话（相当于开一次数据库操作上下文）
        db_session = SessionLocal()
        # yield 把会话"借"给调用方，函数在这里暂停
        yield db_session
    finally:
        # 不管成功失败，最后都关掉，避免连接泄漏
        await db_session.close()