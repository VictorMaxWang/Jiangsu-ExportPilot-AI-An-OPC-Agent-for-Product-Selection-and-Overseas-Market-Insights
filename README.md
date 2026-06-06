# 苏品智航 / Jiangsu ExportPilot

## 项目简介

苏品智航是面向江苏制造企业的 AI 选品与海外市场洞察平台。项目用于江苏高校“丝路电商”创新挑战赛 OPC 智能体应用赛道，目标是把企业资料、产品图片、CSV 样本、公有数据源和阿里云百炼 `qwen3.6-plus` 分析整合到一个可演示、可复核、可人工确认的跨境出海工作流中。

线上演示地址：`https://opc.ankangyu.cn`

系统定位不是替代企业正式尽调，而是把“企业建档、商品录入、市场机会研判、营销草稿、报告版本管理”串成低成本的预研闭环。每个关键结论都保留来源说明、置信度、人工确认入口和 fallback 兜底。

## 核心能力

- 企业建档：支持企业照片或资料截图上传，生成企业草稿；用户确认后再写入正式企业库。
- 多图商品录入：支持最多 8 张商品图片或截图合并识别，提取名称、类目、材质、规格、卖点、目标用户、价格参考和证据摘录。
- 链接兜底：国内商品链接只做公开可访问页面的基础解析；登录、验证码、风控、超时或结构不可解析时提示上传截图。
- 五大洲目标市场：目标国家目录覆盖亚洲、欧洲、北美、拉美、大洋洲和非洲，分析流程可按国家组合生成机会评分。
- 数据源融合：接入 Bailian、World Bank、GDELT、YouTube、Etsy、UN Comtrade，并保留 CSV fallback、缓存和调用日志。
- 市场洞察看板：用 ECharts 展示国家推荐、机会评分、竞品价格区间、内容主题和风险提示。
- 营销内容生成：生成英文标题、五点描述、短视频脚本和运营方向，保持来源边界和人工复核要求。
- 全局聊天：可在产品、分析、看板和报告上下文中解释数据来源、风险边界和下一步操作。
- 报告修改与版本：聊天只生成报告修改 proposal，用户确认后才创建新报告版本；旧版本保留，可查看和恢复。
- 安全与部署：第三方 Key 只由后端读取；生产使用 Docker Compose、Nginx/宝塔反代和腾讯云 CVM。

## Demo 路径

推荐 5 分钟现场演示路径：

1. `/companies/import`：拍照或上传企业资料图，生成企业草稿并人工确认。
2. `/products/import`：上传多张商品截图，生成商品草稿并确认入库。
3. `/analysis/run`：选择企业、商品和五大洲目标国家组合，启动出海分析。
4. `/dashboard/{analysis_id}`：查看国家推荐、机会评分、竞品和内容趋势。
5. `/chat` 或全局聊天浮窗：询问“为什么推荐这些国家”“数据源是否可信”“风险在哪里”。
6. `/reports` 与 `/reports/{id}`：查看报告、版本列表、聊天生成的修改建议和确认保存后的新版本。

比赛材料位于：

- `docs/competition/DEMO_SCRIPT_5MIN.md`
- `docs/competition/JUDGES_QA.md`
- `docs/competition/PPT_OUTLINE_15P.md`

部署材料位于：

- `docs/DEPLOYMENT_TENCENT_CLOUD.md`
- `docs/nginx/opc.ankangyu.cn.conf`

## 本地启动

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
- `BAILIAN_VISION_ENABLED`、`BAILIAN_VISION_MODEL`：控制商品和企业图片识别是否调用真实视觉/多模态模型。
- `PRODUCT_UPLOAD_DIR`、`MAX_PRODUCT_IMAGE_SIZE_MB`：商品图片上传目录和单图大小限制。
- `COMPANY_UPLOAD_DIR`、`MAX_COMPANY_IMAGE_SIZE_MB`：企业照片上传目录和单图大小限制。
- `YOUTUBE_DATA_API_KEY`：YouTube Data API v3 后端凭据；缺失、禁用或失败时使用 seed fallback。
- `ETSY_KEYSTRING`、`ETSY_SHARED_SECRET`：Etsy Open API 后端凭据；缺失、禁用或失败时使用 seed fallback。
- `UN_COMTRADE_API_KEY`：UN Comtrade 可选凭据；后端优先 no-key-first，失败时回落到 seed fallback。
- `ENABLE_YOUTUBE`、`ENABLE_ETSY`、`ENABLE_UN_COMTRADE`：控制对应真实 provider 是否启用。
- `DATA_COLLECTION_CONCURRENCY`：外部数据收集并发上限，用于保证多国家分析速度。
- `EBAY_CLIENT_ID`、`EBAY_CLIENT_SECRET`、`RAKUTEN_APP_ID`、`RAKUTEN_APPLICATION_ID`、`REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET`、`REDDIT_REDIRECT_URI`：P2 future provider 预留配置，当前不作为 MVP runtime 依赖。
- `FRONTEND_URL`、`BACKEND_URL`、`NEXT_PUBLIC_API_BASE_URL`、`CORS_ORIGINS`：本地和部署访问地址配置。

## 安全说明

- 不要提交 `.env`、真实 API Key、Token、Cookie、数据库密码或云服务凭据。
- 第三方 API Key 只能由后端从环境变量读取，不能进入前端代码、构建产物、页面响应或日志。
- 前端只能展示“已配置 / 未配置”等状态，不能展示密钥明文、部分明文、哈希或可恢复的掩码。
- 日志、异常、截图和导出的报告中不得包含密钥、认证头或完整敏感连接串。
- 企业照片和商品截图必须先裁剪隐私信息；运行时上传目录不得提交 GitHub。
- 聊天修改报告只生成 proposal，不直接覆盖当前报告；用户确认后才保存新版本。
- 如果发现密钥被写入仓库或日志，应立即停止相关任务，在对应 `docs/status/*_*.md` 记录风险位置和影响范围，不写入密钥明文。
