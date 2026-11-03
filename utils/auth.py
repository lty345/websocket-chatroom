# =============================================================================
# utils/auth.py —— JWT 签发与校验（整个鉴权体系的核心）
# =============================================================================
# 【JWT 是什么，用一个比喻理解】
#   token 就像一张"盖了章的门票"：
#     签发时（登录成功）：服务器用密钥盖章 → 票上写着"我是谁、什么时候过期"
#     校验时（每次请求）：服务器验章的真伪 → 章是真的就认，不需要查数据库
#
#   门票上的内容（payload）是明文可见的（谁都能 base64 解码看到），
#   但**改不了** —— 改一个字，章就对不上，校验失败。
#   ★ 所以：token 里绝对不能放密码等敏感信息。
#
# 【为什么用 JWT 而不是 Session】
#   传统 Session 要在服务器端存一份"谁登录了"，多台服务器要共享；
#   JWT 是自包含的，服务器不用存任何东西 → 天然支持多台机器。
#   代价：签发后无法主动作废（除非引入黑名单），只能等它过期。
#
# 【它在链路里的位置】
#   1) HTTP 登录：api/user.py 的 login_action → token_encode() → 返回给前端
#   2) WebSocket 握手：api/WebSocket.py 从 URL 参数拿 token → token_decode()
#      （因为浏览器原生 WebSocket 不能自定义请求头，只能把 token 放在 URL 里）
#   3) 其它需要鉴权的接口：短链项目里用 OAuth2 scheme 从 Authorization 头取
# =============================================================================
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from jose import jwt, JWTError
from fastapi import HTTPException, status

# ★ 三个关键参数
#   SECRET_KEY : 盖章用的印泥。泄露 = 谁都能伪造 token。
#                生产必须放环境变量，且要足够随机（这行原本是硬编码的弱密钥）。
#   ALGORITHM  : HS256 = 对称加密（加密解密用同一个密钥），简单但要求密钥保密。
#                另一种 RS256 = 非对称（私钥签、公钥验），适合多服务架构。
#   EXPIRE     : 15 分钟过期。短一点更安全，但用户体验差（要频繁续期）。
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15


class AuthTokenHelper:

    @staticmethod
    def token_encode(data: dict, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
        """生成 JWT Token（登录成功后调用）"""
        # 复制一份，避免改到调用方传进来的 dict
        to_encode = data.copy()

        # 标准声明（JWT 规范里约定的字段名）：
        #   exp = 过期时间（带时区，必须用 UTC，否则不同时区会算错）
        #   iat = 签发时间
        expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
        to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})

        # ★ 注意：这里 update 会**覆盖**调用方自己传的 exp。
        #   api/user.py 里明明写了 exp=2 天，但这里会被 15 分钟覆盖掉 ——
        #   实际生效的是 15 分钟。要改成 2 天，得改 expires_minutes 参数。
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def token_decode(token: str) -> Optional[Dict[str, Any]]:
        """解析并验证 JWT Token（每次请求校验时调用）"""
        # 先准备好"校验失败要抛的异常"。
        # headers={"WWW-Authenticate": "Bearer"} 是 HTTP 规范要求 401 时带的头，
        # 告诉客户端"请用 Bearer 方式携带凭证"。
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无法验证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            # decode 会做三件事：
            #   1) 用同一个密钥重新算签名，对不上就抛 JWTError（= 票是假的）
            #   2) 检查 exp，过期了抛 ExpiredSignatureError（JWTError 的子类）
            #   3) 签名和过期都过了，返回 payload（票上的内容）
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            # 签名错 / 过期 / 格式错，统一转成 401
            raise credentials_exception