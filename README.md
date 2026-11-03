# 实时聊天室

基于 **FastAPI + WebSocket + Redis Pub/Sub** 的多人实时聊天室，支持房间级消息广播、在线名单同步与 JWT 握手鉴权。

## 技术栈

| 分类 | 选型 |
|---|---|
| 长连接 | Starlette `WebSocketEndpoint` |
| 广播 | Redis Pub/Sub（三个频道：登录 / 登出 / 消息） |
| 认证 | JWT（python-jose / HS256，15 分钟过期） |
| 数据 | SQLAlchemy + MySQL |
| 前端 | Vue 2（注册 / 登录 / 聊天室 三页面） |

## 核心实现

### 1. 连接管理

自研 `RoomConnectionManager` 维护「用户 → WebSocket 连接」映射，支持：
- 用户上线 / 下线时广播系统通知
- 在线名单实时同步
- 同一账号重复登录时踢掉旧连接（`WS_1008` 主动断开）

### 2. Redis Pub/Sub 广播

消息生产与推送解耦：

```
客户端发消息 → 服务端 publish 到 Redis 频道
                          ↓
           所有订阅该频道的进程 subscribe 到 → 各自推给自己持有的连接
```

好处：多进程 / 多实例部署时，在线状态与消息流仍能共享，不依赖单机内存。

### 3. 握手鉴权

浏览器原生 WebSocket **不支持自定义请求头**，因此 token 通过 query 参数传递：

```
ws://host/ws/chat?token=<jwt>
```

握手阶段校验 JWT，缺失或非法直接拒绝连接。

### 4. 会话与档案分离

- **在线会话**：内存中的活动连接（`RoomConnectionManager`）
- **用户档案**：数据库持久化（用户名、密码哈希、注册时间）

两者分离建模，避免「服务重启后用户档案丢失」和「档案查询拖慢连接操作」。

## 快速开始

```bash
uv sync
cp .env.example .env      # 填 SECRET_KEY / MySQL 连接
uv run uvicorn main:app --reload
```

前端页面：`user_register.html` / `user_login.html` / `chat_room.html`

## 项目结构

```
├── main.py                   应用入口
├── api/                      注册 / 登录 / WebSocket 端点
├── RoomConnectionManager.py  连接管理与广播
├── models/                   ORM 模型
├── schemas/                  出入参模型
├── servies/                  业务逻辑
├── utils/                    JWT / 密码哈希
└── *.html                    Vue 2 前端页面
```