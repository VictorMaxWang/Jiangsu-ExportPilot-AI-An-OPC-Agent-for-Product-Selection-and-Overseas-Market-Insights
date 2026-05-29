# 系统架构

## 总体架构

苏品智航采用前后端分离架构：

- Next.js 前端负责产品录入、智能导入、草稿确认、看板展示、配置状态显示和报告预览。
- FastAPI 后端负责业务 API、Product Intake、数据源接入、AI 调用、评分计算和报告生成。
- PostgreSQL 保存产品、产品导入任务与草稿、数据源结果、评分、AI 生成内容和报告记录。
- 外部 API 与阿里云百炼只从后端访问。
- CSV fallback 用于无 Key、网络异常或比赛现场演示兜底。

```text
User
  -> Next.js frontend
  -> FastAPI backend
  -> Product Intake
  -> PostgreSQL
  -> External API clients
  -> Alibaba Cloud Bailian qwen3.6-plus / vision model
  -> CSV fallback data
```

## 前端结构

建议目录：

```text
frontend/
├── app/
├── components/
├── features/
├── lib/
├── styles/
└── tests/
```

前端职责：

- 产品录入表单、CSV 上传入口、智能商品导入页面和产品草稿确认入口。
- 市场洞察看板，包括评分卡、趋势图、国家对比和平台信号。
- 报告预览与导出入口。
- 管理页展示后端返回的 API 配置状态。
- 不读取、不缓存、不展示任何第三方 API Key。

## 后端结构

建议目录：

```text
backend/
├── app/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── clients/
│   └── workers/
└── tests/
```

后端职责：

- 提供 REST API 给前端。
- 读取环境变量和应用配置。
- 管理数据库连接、迁移和模型。
- 封装 Product Intake 流程，包括截图上传、单链接安全解析、Qwen 商品理解、草稿保存和确认入库。
- 封装外部数据源客户端。
- 封装阿里云百炼 `qwen3.6-plus` 调用。
- 实现市场机会评分、营销文案生成和报告生成。
- 提供 API Key 配置状态，但不返回明文。

## Product Intake 模块

Product Intake 用于把用户主动提供的商品截图、产品目录截图、单个国内商品链接或手动文本整理成可确认的产品草稿。

```text
frontend intake page
  -> backend product intake API
  -> Screenshot Intake / URL Intake / manual text
  -> Qwen Product Understanding
  -> product_drafts
  -> Product Draft Review
  -> Confirm to Product
  -> existing analysis workflow
```

模块边界：

- Screenshot Intake：接收用户上传的淘宝、拼多多、京东商品详情页截图或企业产品目录截图，校验 MIME、大小、尺寸和存储路径，只保存商品理解所需图片和元数据。
- URL Intake：仅处理用户主动提交的单个商品 URL，识别平台并尝试读取公开可访问页面基础信息；遇到登录、验证码、风控、访问受限、超时或结构不可解析时失败，并提示用户上传截图。
- Qwen Product Understanding：由后端集中调用 Qwen 视觉/多模态模型，按固定 JSON 契约提取商品字段、证据、风险和置信度；前端不得直接调用 Bailian 或持有 Key。
- Product Draft Review：AI 提取结果先保存为 `product_drafts`，前端展示证据、置信度和风险提示，用户可编辑草稿字段。
- Confirm to Product：只有用户确认后才创建正式 `products` 记录；被拒绝或低置信度失败的草稿不得进入分析流程。

合规边界：

- 不绕过登录、验证码、风控、签名校验、App 私有接口或平台访问限制。
- 不做搜索结果、列表页、店铺页、分页或批量采集。
- 不承诺能解析所有淘宝、拼多多、京东页面。
- 截图和链接解析结果只能表述为用户提供材料和 AI/页面可见信息提取，不得表述为平台官方验证数据。

## 数据库设计方向

核心实体建议：

- `products`：企业产品与基础属性。
- `product_import_jobs`：一次截图、链接或手动文本导入任务。
- `product_import_assets`：导入任务关联的截图文件和元数据。
- `product_drafts`：AI 或解析流程生成的待确认产品草稿。
- `domestic_product_links`：用户主动提交的国内商品链接解析记录。
- `market_requests`：一次市场分析请求。
- `source_snapshots`：外部 API 或 CSV 的标准化数据快照。
- `market_scores`：市场机会评分和维度分。
- `ai_outputs`：AI 摘要、解释、文案和报告段落。
- `reports`：出海报告元数据和导出内容路径。

数据库只保存业务必要数据，不保存第三方 API Key。

## AI 调用结构

阿里云百炼调用必须集中在后端服务中：

```text
frontend request
  -> backend analysis / product intake service
  -> prompt builder
  -> Bailian client
  -> response parser
  -> scoring/report/product draft service
  -> database
  -> frontend response
```

AI 输出必须记录：

- 使用模型：`qwen3.6-plus` 或通过 `BAILIAN_VISION_MODEL` 配置的视觉/多模态模型。
- 输入摘要，不记录敏感 Key。
- 输出内容。
- 生成时间。
- 失败原因或 fallback 状态。

## 外部 API 接入

所有外部 API 通过后端 provider/service 封装。当前 P0/P1 runtime 数据源为：

- World Bank：宏观经济与国家指标。
- GDELT：新闻与舆情趋势。
- UN Comtrade：贸易流向与品类进出口数据。
- YouTube Data API：视频内容趋势。
- Etsy Open API：手工与设计类商品趋势。

P2 future provider 仅保留扩展方向，当前没有 runtime client，不阻塞 MVP：

- eBay Browse API：跨境电商商品与价格参考。
- Rakuten Ichiba：日本市场商品信号。
- Reddit API：社区讨论和用户需求信号。

每个客户端应输出统一结构，便于评分服务消费。

## CSV Fallback

CSV fallback 是比赛演示的核心兜底能力：

- 当前样本和 fallback 文件集中放在 `data/seed/`。
- 标准化后的 fallback 数据可来自 `data/seed/*` 或数据库快照。
- 当 API Key 缺失、配额不足、网络失败或接口变更时，后端返回 fallback 数据并标记来源。
- 前端需要清晰显示数据来源，例如 `API`、`CSV fallback`、`mock sample`。

## 部署结构

Docker Compose 建议服务：

- `frontend`：Next.js 应用。
- `backend`：FastAPI 应用。
- `db`：PostgreSQL。
- `nginx`：反向代理和静态入口。

腾讯云服务器部署建议：

```text
Internet
  -> Nginx 80/443
  -> frontend container
  -> backend container
  -> db container or managed PostgreSQL
```

生产环境要求：

- `.env` 只存在服务器或部署 Secret 配置中。
- Nginx 负责域名、HTTPS、压缩和反向代理。
- 后端限制 CORS 到前端域名。
- 日志中不得出现 API Key、Token、Secret 或完整认证头。
