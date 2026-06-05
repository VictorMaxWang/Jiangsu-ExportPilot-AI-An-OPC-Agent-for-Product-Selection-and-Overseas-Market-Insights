# 系统架构

## 总体架构

苏品智航采用前后端分离架构：

- Next.js 前端负责产品录入、智能导入、企业拍照录入、草稿确认、目标市场选择、全局聊天、看板展示、配置状态显示和报告预览。
- FastAPI 后端负责业务 API、Product Intake、Company Intake、Target Market Catalog、Global Chat、Report Versioning、数据源接入、AI 调用、评分计算和报告生成。
- PostgreSQL 保存企业与产品、导入任务与草稿、目标市场目录、聊天会话、报告修改 proposal、报告版本、数据源结果、评分、AI 生成内容和报告记录。
- 外部 API 与阿里云百炼只从后端访问。
- CSV fallback 用于无 Key、网络异常或比赛现场演示兜底。

```text
User
  -> Next.js frontend
  -> FastAPI backend
  -> Product Intake / Company Intake / Global Chat
  -> PostgreSQL
  -> Target Market Catalog
  -> External API clients
  -> Alibaba Cloud Bailian qwen3.6-plus / vision model
  -> Report Versioning
  -> CSV fallback data
```

## Role Plugin Adaptation 边界

Q40 参考 `openai/role-specific-plugins` 时，只把 Data Analytics、Sales、Product Design 和 Financial Markets 中的工作流方法翻译为本项目架构约束。

可借鉴：

- Data Analytics 的来源验证、fallback 标记、caveat、报告结构和分析 QA 方法。
- Sales 的草稿、审阅、修改、确认后写入流程。
- Product Design 的 brief 确认、真实界面证据、响应式和可访问性审查方法。
- Financial Markets 的 source posture、事实/假设/推导标签、stale data 和 evidence gap 表述纪律。

不可借鉴：

- 不复制插件代码、技能原文、runtime widget、MCP server、脚本、测试、assets、templates、品牌素材或 marketplace 元数据。
- 不复制 `.app.json` 里的 connector app id、OAuth/client id、workspace 绑定或任何外部 workspace 配置。
- 不把插件 connector/source registry 作为本项目后端来源；Target Market Catalog、Global Chat、Report Versioning 必须由本项目 FastAPI 服务、PostgreSQL 模型和安全策略实现。
- 不让全局聊天绕过 proposal/confirm 规则；聊天只能解释、引用、生成 proposal，用户确认后才进入正式版本保存。

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

- 产品录入表单、CSV 上传入口、多图智能商品导入页面和产品草稿确认入口。
- 企业管理、企业拍照录入入口和企业草稿确认入口。
- 目标市场选择组件通过后端 Target Market Catalog 获取国家、区域、启停状态和默认组合，前端不得写死国家列表。
- 市场洞察看板，包括评分卡、趋势图、国家/区域对比和平台信号。
- 全局 AI 聊天窗口，能携带当前企业、产品、分析和报告上下文请求后端，不在前端拼接敏感提示词或保存 Key。
- 报告预览、报告解析、修改 proposal 确认和版本切换入口。
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
- 封装 Product Intake 流程，包括多图上传、单链接安全解析、Qwen 商品理解、草稿保存和确认入库。
- 封装 Company Intake 流程，包括企业资料图片上传、Qwen 企业信息理解、`company_drafts` 保存和确认入库。
- 封装 Target Market Catalog，统一管理国家、市场区域、启停状态、默认目标组合和分析可用性。
- 封装 Global Chat，上下文只从后端受控读取，支持报告解析、分析解释和报告修改 proposal 生成。
- 封装 Report Versioning，聊天或报告编辑只生成 proposal，用户确认后才保存新版本。
- 封装外部数据源客户端。
- 封装阿里云百炼 `qwen3.6-plus` 调用。
- 实现市场机会评分、营销文案生成和报告生成。
- 提供 API Key 配置状态，但不返回明文。

## Product Intake 模块

Product Intake 用于把用户主动提供的多张商品图片、产品目录截图、单个国内商品链接或手动文本整理成可确认的产品草稿。

```text
frontend intake page
  -> backend product intake API
  -> Multi-image Intake / URL Intake / manual text
  -> Qwen Product Understanding
  -> product_drafts
  -> Product Draft Review
  -> Confirm to Product
  -> existing analysis workflow
```

模块边界：

- Multi-image Intake：接收用户上传的淘宝、拼多多、京东商品详情页截图、产品主图、包装图、规格表、资质图或企业产品目录截图，校验 MIME、大小、尺寸、数量和存储路径，只保存商品理解所需图片和元数据。
- URL Intake：仅处理用户主动提交的单个商品 URL，识别平台并尝试读取公开可访问页面基础信息；遇到登录、验证码、风控、访问受限、超时或结构不可解析时失败，并提示用户上传截图。
- Qwen Product Understanding：由后端集中调用 Qwen 视觉/多模态模型，按固定 JSON 契约合并多图证据并提取商品字段、证据、风险和置信度；前端不得直接调用 Bailian 或持有 Key。
- Product Draft Review：AI 提取结果先保存为 `product_drafts`，前端展示证据、置信度和风险提示，用户可编辑草稿字段。
- Confirm to Product：只有用户确认后才创建正式 `products` 记录；被拒绝或低置信度失败的草稿不得进入分析流程。

合规边界：

- 不绕过登录、验证码、风控、签名校验、App 私有接口或平台访问限制。
- 不做搜索结果、列表页、店铺页、分页或批量采集。
- 不承诺能解析所有淘宝、拼多多、京东页面。
- 截图和链接解析结果只能表述为用户提供材料和 AI/页面可见信息提取，不得表述为平台官方验证数据。

## Company Intake 模块

Company Intake 用于把用户拍摄或上传的企业资料图片整理成可确认的企业草稿。

```text
company photo / business card / catalog cover
  -> backend company intake API
  -> Qwen Company Understanding
  -> company_drafts
  -> Company Draft Review
  -> Confirm to Company
  -> existing product and analysis workflow
```

模块边界：

- Company Photo Intake：接收营业执照、企业名片、展会资料、产品目录封面等用户主动上传的图片，校验文件类型、大小、数量和存储路径。
- Qwen Company Understanding：后端调用视觉/多模态模型提取企业名称、地区、行业、联系人角色、主营品类、官网或简介等草稿字段，并记录字段证据和置信度。
- Company Draft Review：AI 提取结果先保存为 `company_drafts`，前端展示证据、低置信度提示和可编辑字段。
- Confirm to Company：只有用户确认后才创建正式 `companies` 记录；拒绝草稿或识别失败不得自动入库。

合规边界：

- 上传前提示用户遮挡身份证号、手机号、详细地址、合同金额、账号、二维码私密信息等不必要内容。
- OCR 和 AI evidence 只保存企业建档必要摘录，不保存完整证照 OCR、完整图片文本或敏感个人信息。
- 企业拍照录入只用于用户主动建档，不用于批量识别企业、爬取企业库或对外背书企业资质真实性。

## Target Market Catalog 模块

Target Market Catalog 是后端维护的目标国家与市场区域目录，前端不得写死国家列表。

```text
admin/catalog seed or backend config
  -> target_market_regions / target_market_countries
  -> market selector API
  -> analysis request
  -> provider/data-source country mapping
  -> scoring and report workflow
```

模块边界：

- Market Region：支持北美、欧洲、东亚、东南亚、南亚、中东、非洲、拉美、澳新等市场区域，数量可扩展，不限制为 5 个固定区域。
- Market Country：保存 ISO 国家代码、中文名、英文名、所属区域、是否启用、是否支持 fallback、默认排序、推荐行业标签和分析可用性。
- Catalog API：前端通过后端接口获取可选国家、区域分组、默认目标市场组合和禁用原因。
- Analysis Integration：分析请求只接受目录中启用且可分析的国家代码；provider 层负责把目录国家映射到 World Bank、GDELT、UN Comtrade、YouTube、Etsy 或 fallback 所需参数。

## Global Chat 模块

Global Chat 提供跨页面 AI 聊天窗口，支持解释分析结果、解析报告和发起报告修改建议。

```text
frontend global chat
  -> backend chat API
  -> context resolver
  -> Bailian qwen3.6-plus
  -> chat_sessions / chat_messages
  -> report_edit_proposals when editing report
```

模块边界：

- Context Resolver：后端根据用户当前页面、安全权限和请求类型读取企业、产品、分析、看板、营销内容和报告上下文；前端只传上下文 ID，不拼接完整敏感上下文。
- Report Parser：聊天可以引用报告章节、段落标题和关键指标，返回定位信息、解释和证据摘要。
- Proposal Generator：当用户要求修改报告时，聊天只创建 `report_edit_proposals`，内容包括目标报告版本、修改意图、建议 diff/替换段落、风险提示和置信度。
- User Confirmation：用户确认 proposal 后才进入 Report Versioning 保存新版本；未确认 proposal 不改变报告正文。

安全边界：

- 聊天日志和上下文摘要不得记录 Key、Cookie、认证头、完整敏感连接串、完整第三方 HTML、完整 OCR 或用户不必要隐私。
- 聊天回答不得编造销量、认证、交易额、税务结论、法律结论或保证性市场收益。

## Report Versioning 模块

Report Versioning 用于保留报告原始版本、AI 修改 proposal 和用户确认后的新版本。

```text
reports
  -> report_versions
  -> report_edit_proposals
  -> user confirm proposal
  -> new report_versions row
  -> current report version pointer
```

模块边界：

- `reports` 保存报告主记录和当前版本指针。
- `report_versions` 保存每一次确认后的 Markdown/HTML 内容、来源类型、父版本、创建时间和版本说明。
- `report_edit_proposals` 保存 AI 或用户编辑生成的待确认修改建议，不直接覆盖任何版本。
- 版本切换和对比由后端返回版本列表、当前版本、父版本和 proposal 来源；前端负责展示差异和确认按钮。
- 删除或回滚策略在后续实现任务中定义，Q40 只要求确认后新增版本、原版本保留。

## 数据库设计方向

核心实体建议：

- `products`：企业产品与基础属性。
- `product_import_jobs`：一次截图、链接或手动文本导入任务。
- `product_import_assets`：导入任务关联的截图文件和元数据。
- `product_drafts`：AI 或解析流程生成的待确认产品草稿。
- `domestic_product_links`：用户主动提交的国内商品链接解析记录。
- `company_import_jobs`：一次企业资料图片或文本导入任务。
- `company_import_assets`：企业导入任务关联的图片文件和元数据。
- `company_drafts`：AI 或 OCR 流程生成的待确认企业草稿。
- `target_market_regions`：后端维护的市场区域目录。
- `target_market_countries`：后端维护的目标国家目录、区域归属、启停状态和 provider 映射。
- `market_requests`：一次市场分析请求。
- `source_snapshots`：外部 API 或 CSV 的标准化数据快照。
- `market_scores`：市场机会评分和维度分。
- `ai_outputs`：AI 摘要、解释、文案和报告段落。
- `reports`：出海报告元数据和导出内容路径。
- `report_versions`：报告确认版本、父版本和当前版本内容。
- `report_edit_proposals`：聊天或编辑生成的待确认报告修改建议。
- `chat_sessions`：全局聊天会话元数据。
- `chat_messages`：聊天消息、上下文引用和脱敏 AI 输出。

数据库只保存业务必要数据，不保存第三方 API Key。

## AI 调用结构

阿里云百炼调用必须集中在后端服务中：

```text
frontend request
  -> backend analysis / product intake / company intake / global chat service
  -> prompt builder
  -> Bailian client
  -> response parser
  -> scoring/report/product draft/company draft/proposal service
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
