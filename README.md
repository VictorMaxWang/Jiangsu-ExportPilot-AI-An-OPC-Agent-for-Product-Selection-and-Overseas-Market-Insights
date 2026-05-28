# 苏品智航 / Jiangsu ExportPilot

## 项目简介

苏品智航是面向江苏制造企业的 AI 选品与海外市场洞察平台。项目用于江苏高校“丝路电商”创新挑战赛 OPC 智能体应用赛道，目标是把产品信息、CSV 样本、公有数据源和阿里云百炼 `qwen3.6-plus` 分析整合到一个可演示的跨境出海决策工作流中。

核心能力包括产品录入、样本数据导入、海外市场机会评分、营销文案生成、趋势可视化、API 配置状态展示和出海分析报告导出。

## 本地启动

T01 已提供可运行的 Next.js 前端骨架和 FastAPI 后端骨架。

前端：

```powershell
cd frontend
npm install
npm run dev -- --hostname 127.0.0.1 --port 3000
```

访问 `http://localhost:3000`。

后端：

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

健康检查：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health
```

预期返回：

```json
{"status":"ok","service":"supinzhihang-backend"}
```

## Docker Compose 启动

准备环境变量：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，至少替换 `POSTGRES_PASSWORD`，并让 `DATABASE_URL` 中的密码保持一致。需要调用外部平台时，再填写对应 API Key。

启动服务：

```powershell
docker compose up --build
```

Compose 服务约定：

- `frontend`：Next.js 前端，宿主机端口默认 `3000`，构建上下文 `./frontend`。
- `backend`：FastAPI 后端，宿主机端口默认 `8000`，构建上下文 `./backend`。
- `postgres`：PostgreSQL 16，默认数据库 `supinzhihang`。
- `redis`：Redis 7，用于缓存、任务队列或临时状态。

## 环境变量

根目录 `.env.example` 只包含占位符和本地示例值，不包含真实密钥。

常用变量：

- `DATABASE_URL`：后端连接 PostgreSQL 的地址，Compose 内部主机名使用 `postgres`。
- `REDIS_URL`：后端连接 Redis 的地址，Compose 内部主机名使用 `redis`。
- `DASHSCOPE_API_KEY`、`BAILIAN_API_KEY`：阿里云百炼 / DashScope API Key，仅后端读取。当前后端优先读取 `DASHSCOPE_API_KEY`，并兼容 `BAILIAN_API_KEY`。
- `BAILIAN_BASE_URL`：默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`。
- `BAILIAN_MODEL`：默认 `qwen3.6-plus`。
- `YOUTUBE_DATA_API_KEY`：YouTube Data API v3 后端凭据；缺失、禁用或失败时使用 seed fallback。
- `ETSY_KEYSTRING`、`ETSY_SHARED_SECRET`：Etsy Open API 后端凭据；缺失、禁用或失败时使用 seed fallback。
- `UN_COMTRADE_API_KEY`：UN Comtrade 可选凭据；后端优先 no-key-first，失败时回落到 seed fallback。
- `ENABLE_YOUTUBE`、`ENABLE_ETSY`、`ENABLE_UN_COMTRADE`：控制对应真实 provider 是否启用。
- `EBAY_CLIENT_ID`、`EBAY_CLIENT_SECRET`、`RAKUTEN_APP_ID`、`RAKUTEN_APPLICATION_ID`、`REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET`、`REDDIT_REDIRECT_URI`：P2 future provider 预留配置，当前不作为 MVP runtime 依赖。
- `FRONTEND_URL`、`BACKEND_URL`、`NEXT_PUBLIC_API_BASE_URL`、`CORS_ORIGINS`：本地和部署访问地址配置。

## 安全说明

- 不要提交 `.env`、真实 API Key、Token、Cookie、数据库密码或云服务凭据。
- 第三方 API Key 只能由后端从环境变量读取，不能进入前端代码、构建产物、页面响应或日志。
- 前端只能展示“已配置 / 未配置”等状态，不能展示密钥明文、部分明文、哈希或可恢复的掩码。
- 日志、异常、截图和导出的报告中不得包含密钥、认证头或完整敏感连接串。
- 如果发现密钥被写入仓库或日志，应立即停止相关任务，在对应 `docs/status/*_*.md` 记录风险位置和影响范围，不写入密钥明文。
