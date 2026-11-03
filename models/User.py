# =============================================================================
# models/User.py —— 数据库表：用户档案
# =============================================================================
# 【它在链路里的位置】
#   这是"存进数据库的那份用户资料"。
#   注意和 models/OnlineUser.py 区分：
#     User       = 数据库里的一行（会一直存在）
#     OnlineUser = 此刻连着的那个人（连接一断就没了）
#
# 【★ 这个表有两个真实问题，复习时特别注意】
#   1) password 用的是明文存储（String(32)），登录时直接比对明文。
#      正确做法是存 bcrypt 哈希（60 字符），列宽要 >= 60。
#      短链项目里的 utils/password.py 就是正确写法，可以对照看。
#   2) phone_number 用 Integer 存手机号：
#      SQLite 无所谓，但换成 MySQL 的 INT 会溢出
#      （手机号 13725859364 > INT 上限 2147483647）
#      → 必须用 BIGINT 或 VARCHAR(11)。
# =============================================================================
from typing import Mapping

from db.database import Base
from sqlalchemy import Column, String, DateTime, func, Integer


class User(Base):
    __tablename__ = 'User'

    # username 直接做主键（设计上有点怪，一般用自增 id 做主键，username 加唯一索引）
    # 这里写的 Mapping[str] 类型标注其实不起作用，SQLAlchemy 只认 Column(...)，
    # 保持原样即可，理解为"给 IDE 看的注释"
    username: Mapping[str] = Column(String(20), primary_key=True)

    # ★ 明文密码列，且只有 32 位（bcrypt 哈希是 60 位，换成哈希必须加宽）
    password: Mapping[str] = Column(String(32))

    # ★ Integer 存手机号在 SQLite 能跑，换 MySQL 会溢出
    phone_number: Mapping[str] = Column(Integer)