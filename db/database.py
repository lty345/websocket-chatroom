# =============================================================================
# db/database.py —— 数据库连接层（创建引擎、会话工厂、模型基类）
# =============================================================================
# 【它在链路里的位置】
#   最底层。所有 models/*.py 都继承这里的 Base；
#   dependencies/dependencies.py 用这里的 SessionLocal 生产数据库会话。
#
#   启动流程：main.py 的 lifespan → 用 async_engine 建表
#   请求流程：路由函数 → Depends(get_db_session) → SessionLocal() → 查库
#
# 【三个核心对象】
#   async_engine  : 连接池工厂，持有到数据库的连接。全局只需要一个。
#   Base          : 所有 ORM 模型的父类，SQLAlchemy 靠它知道"有哪些表"。
#   SessionLocal  : 会话工厂。调一次 SessionLocal() 就得到一个会话（一次操作）。
#                   ★ 注意 expire_on_commit=False 很重要，
#                     否则 commit 之后再读对象属性会触发额外查询（异步下容易报错）。
# =============================================================================
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

from config.config import get_Settings

# 异步引擎：连接池就在这里管理。echo=False 表示不打印每条 SQL（调试时改 True）
async_engine = create_async_engine(get_Settings().ASYNC_DATABASE_URL, echo=False)

# ORM 模型的基类。models/User.py 里的 class User(Base) 就是继承它
Base = declarative_base()

# 会话工厂：bind 到引擎，class_ 指定异步会话类型
SessionLocal = sessionmaker(bind=async_engine, expire_on_commit=False, class_=AsyncSession)