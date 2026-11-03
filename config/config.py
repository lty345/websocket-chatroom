# =============================================================================
# config/config.py —— 全局配置中心
# =============================================================================
# 【作用】
#   把"会变的东西"集中在一处：数据库地址、密钥。其他文件都从这里取。
#   好处：换环境（本地/SQLite/MySQL）只改这一个文件。
#
# 【用到的技巧】
#   pydantic_settings.BaseSettings：自动读环境变量 + 类型校验。
#     比如定义了 ASYNC_DATABASE_URL，那么设置环境变量 ASYNC_DATABASE_URL=xxx
#     就能覆盖下面写的默认值，不用改代码。
#   @lru_cache：让 get_Settings() 只真正执行一次，之后都返回缓存的同一个对象。
#     否则每次调用都重新读配置，浪费资源。
#
# 【本项目实际用的是】
#   sqlite+aiosqlite:///short.db  → 本地文件数据库，不用装 MySQL，适合练手。
#   ★ 注意这是 SQLite 不是 MySQL，所以简历/文档里别写成 MySQL。
# =============================================================================
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 异步数据库连接串（sqlite + aiosqlite 异步驱动）
    ASYNC_DATABASE_URL: str = ("sqlite+aiosqlite:///short.db")
    # JWT 签名密钥。
    # ★ 生产环境必须放环境变量/密钥管理服务，绝不能硬编码在代码里，
    #   否则代码一泄露 = 谁都能伪造 token。
    TOKEN_SIGN_SECRET: str = 'ZcjT6RcplyIFQoS7'


@lru_cache()
def get_Settings():
    # 带缓存：第一次调用创建 Settings 对象，之后直接复用
    return Settings()