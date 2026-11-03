# =============================================================================
# main.py —— 服务入口（整个聊天室的启动点）
# =============================================================================
# 【启动时会顺序做这些事】
#   ① lifespan 里的准备工作（服务开始接客之前）：
#       - 建表（如果表不存在）
#       - 连接 Redis 并订阅频道
#       - 启动后台任务：循环从 Redis 收消息 → 广播给所有在线用户
#   ② 创建 FastAPI 实例
#   ③ 挂上两组路由：用户接口（HTTP）+ 聊天室（WebSocket）
#
# 【为什么 Redis 那两步要放在启动时】
#   订阅是长期存在的（服务活着就要一直听），不能每个请求都订阅一遍。
#   放在 lifespan 里 = 全进程只执行一次。
# =============================================================================
from contextlib import asynccontextmanager
from fastapi import FastAPI
from api.user import router_user
from api.WebSocket import router_char, room_manager   # room_manager 是全局唯一的连接管理器


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- 启动阶段（yield 之前）--------------------------------------------
    from db.database import Base, async_engine

    # 建表：Base.metadata 里收集了所有继承 Base 的模型（也就是全部表定义）
    # run_sync 是因为 create_all 是同步 API，需要桥接到异步连接上执行
    async def create_table():
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    await create_table()

    # 连接 Redis 并拿到 pubsub 对象（见 RoomConnectionManager.register_pubsub）
    await room_manager.register_pubsub()
    # 订阅 3 个频道 + 启动后台循环，持续把 Redis 消息广播给 WebSocket 客户端
    await room_manager.do_listaction()

    yield   # ← 服务运行期间停在这里

    # ---- 关闭阶段（yield 之后）--------------------------------------------
    await async_engine.close()


app = FastAPI(lifespan=lifespan)

# 两组路由分别负责：
#   router_user : 注册 / 登录（普通 HTTP 接口）
#   router_char : WebSocket 长连接 + 聊天页面
app.include_router(router_user)
app.include_router(router_char)


if __name__ == "__main__":
    import uvicorn
    # reload=True：改代码自动重启（开发用，生产要关掉）
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)