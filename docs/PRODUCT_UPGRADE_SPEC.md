# 产品升级规格

## 目标与边界

本规格用于 Q40 之后的下一轮产品升级设计，目标是把苏品智航从“单产品、少量目标市场、页面级工作流”升级为“多图录入、拍照建档、后端市场目录、全局 AI 聊天和报告版本协作”的产品形态。

本规格只定义产品需求、架构方向和后续任务边界，不创建迁移、不实现 API、不修改业务代码。

固定原则：

- 商品多图录入只生成 `product_drafts`，用户确认后才写入正式 `products`。
- 企业拍照录入只生成 `company_drafts`，用户确认后才写入正式 `companies`。
- 聊天修改报告只生成 `proposal`，用户确认后才保存新 `report_versions`。
- 目标国家按后端国家库和 Target Market Catalog 管理，前端不写死国家列表。
- 所有 AI 输出都是草稿、解释或建议，不作为平台官方验证、法律、关税、投资或确定性销售承诺。

## 插件借鉴边界

本规格参考 `openai/role-specific-plugins` 时，只借鉴方法，不复制插件。借鉴评估详见 `docs/ROLE_PLUGIN_ADAPTATION_PLAN.md`，第三方说明详见 `docs/THIRD_PARTY_NOTICES.md`。

允许借鉴：

- Data Analytics：来源验证、fallback 标记、caveat、报告 QA 和可解释数据展示。
- Sales：proposal 或草稿先审阅，用户确认后才写入正式记录。
- Product Design：先确认 brief，再基于真实界面截图审查上传、聊天、报告编辑和移动端体验。
- Financial Markets：区分事实、假设、推导、过期数据和证据缺口，避免把 AI 解读表述为官方验证。

禁止借鉴：

- 插件实现、connector app id、`.app.json` workspace 绑定、MCP 配置、assets、scripts、templates、品牌素材、默认 prompt 或 marketplace 文案。
- 销售 CRM、投资分析、估值、交易、组合管理或外部消息写入等领域专用能力。
- 任何会绕过本项目后端目录、草稿确认、proposal 确认、隐私过滤或旧版本保留规则的设计。

## 多图商品录入

多图商品录入扩展现有 Product Intake。用户可以为同一产品上传多张图片，系统合并证据后生成一个待确认产品草稿。

支持材料：

- 商品主图、详情页截图、SKU/规格图、包装图、说明书、资质材料、产品目录页。
- 淘宝、拼多多、京东等商品详情页截图，仅限用户主动上传。
- 企业自有产品目录或展会资料中的产品页。

端到端流程：

```text
multiple product images / optional text
  -> Product Intake API
  -> product_import_jobs
  -> product_import_assets[]
  -> Qwen Product Understanding
  -> product_drafts
  -> user review and edit
  -> confirm to products
```

关键规则：

- 一次导入任务可关联多张 `product_import_assets`，每张图片记录类型、顺序、文件元数据和脱敏 evidence 引用。
- 后端负责校验图片 MIME、大小、数量、尺寸和存储路径；前端只展示校验结果和上传状态。
- Qwen 多模态理解必须合并多张图片证据，输出字段证据、冲突提示、置信度和风险说明。
- 图片之间出现价格、规格、材质冲突时，不得自动选择确定答案；必须在 `product_drafts.evidence` 和 `risk_notes` 中提示用户复核。
- `product_drafts.status=draft` 时不得进入分析流程；只有用户确认后创建正式 `products` 记录。
- 用户拒绝草稿时，草稿置为 `rejected`，不创建产品。

建议草稿字段：

- 产品名称、英文名、品类、材质、规格、尺寸、重量、颜色、包装、参考价格、采购成本、卖点、适用场景、目标用户、关键词、图片证据、风险提示、置信度。
- `price_cny` 只表示图片可见参考价，不等同采购成本、成交价或利润空间。
- `cost_price_cny` 只能由用户确认或人工录入，AI 不得默认填成采购成本。

低置信度与失败：

- 关键图片过模糊、商品主体无法识别或 JSON 无法解析时，不创建可确认产品草稿，提示重新上传或手动录入。
- 识别置信度低但能提取部分字段时，可创建低置信度 `product_drafts`，前端必须突出提示并要求逐项确认。
- 不保存订单号、收货人、手机号、地址、聊天记录、账号头像等与商品理解无关的隐私信息。

## 企业拍照录入

Company Intake 用于把企业资料照片整理成企业草稿，降低企业建档成本。

支持材料：

- 营业执照、企业名片、展会资料、产品目录封面、企业宣传册封面。
- 用户手动补充的企业简介、主营品类、地区和联系人角色。

端到端流程：

```text
company photo / company text
  -> Company Intake API
  -> company_import_jobs
  -> company_import_assets[]
  -> Qwen Company Understanding
  -> company_drafts
  -> user review and edit
  -> confirm to companies
```

关键规则：

- 企业拍照先生成 `company_drafts`，用户确认后才创建正式 `companies`。
- `company_drafts` 可以保存企业名称、统一社会信用代码后四位或脱敏标识、地区、行业、主营品类、官网、简介、联系人角色和证据。
- 系统不得把 AI 提取结果表述为企业资质真实性验证。
- 对身份证号、手机号、详细地址、合同金额、银行账号、二维码私密信息等内容，应提示用户遮挡；后端 evidence 只保存建档必要摘录。
- 低置信度或字段冲突时允许生成草稿，但必须提示用户人工确认；无法识别企业主体时不入库。

建议数据模型方向：

- `company_import_jobs`：企业导入任务，保存来源类型、状态、错误原因、模型名和创建时间。
- `company_import_assets`：企业导入图片和元数据，接口不回显本地绝对路径。
- `company_drafts`：待确认企业草稿，保存字段证据、置信度、状态和确认后的 `confirmed_company_id`。

## 目标国家与市场区域扩展

Target Market Catalog 是后端国家库和市场区域目录，负责统一管理分析可选国家。前端不得写死国家、区域、默认国家组合或启停状态。

目标：

- 覆盖五大洲，并允许使用更多跨境电商市场区域，不限制为 5 个固定区域。
- 初始市场区域建议包括北美、欧洲、东亚、东南亚、南亚、中东、非洲、拉美、澳新。
- 后续可继续加入中亚、独联体、欧盟细分、海湾国家、拉美西语区等运营分组。

端到端流程：

```text
Target Market Catalog
  -> regions and countries API
  -> frontend market selector
  -> analysis request with country codes
  -> provider country mapping
  -> scoring / dashboard / report
```

目录字段方向：

- 市场区域：区域代码、中文名、英文名、排序、启停状态、说明。
- 目标国家：ISO 代码、中文名、英文名、所属区域、洲别、货币、语言、默认排序、是否启用、是否可分析、禁用原因。
- Provider 映射：World Bank、GDELT、UN Comtrade、YouTube、Etsy、CSV fallback 所需的国家代码或查询参数。
- 默认组合：比赛演示默认国家、行业推荐国家、区域推荐国家。

分析规则：

- 分析 API 只接受后端目录中 `enabled=true` 且 `analysis_enabled=true` 的国家代码。
- 目录中没有 provider 映射的国家可以先用 CSV fallback 或禁用状态呈现，不得让前端猜测。
- 报告和看板展示国家名称、区域名称、数据来源和 fallback 状态时，以后端目录返回值为准。
- 国家扩展不能破坏现有 `US`、`JP`、`GB` 等演示路径。

## 全局 AI 聊天

Global Chat 是跨页面固定入口，用户可以在企业、产品、分析、看板和报告页面询问系统当前结果。

能力范围：

- 解释产品草稿字段来源、低置信度原因和补充资料建议。
- 解释目标市场评分、风险、数据来源和 fallback 状态。
- 解析报告结构，定位章节、段落和关键结论。
- 根据用户指令生成报告修改 proposal。

端到端流程：

```text
global chat window
  -> chat request with context ids
  -> backend context resolver
  -> Qwen chat
  -> chat_sessions / chat_messages
  -> optional report_edit_proposals
```

上下文规则：

- 前端只传企业 ID、产品 ID、分析 ID、报告 ID、当前页面和用户问题；后端负责读取受控上下文。
- 后端上下文摘要必须脱敏并限制长度，不传 Key、Cookie、认证头、完整连接串、完整 OCR、整页 HTML 或无关隐私。
- 聊天消息保存用户问题、AI 答复、上下文引用和安全状态，不保存敏感凭据。
- 聊天可以建议用户补充图片、修正草稿、重新选择国家或生成报告 proposal，但不能直接执行高影响写操作。

失败与安全：

- 当上下文不存在、无权限、报告版本不存在或 AI 调用失败时，返回可解释错误和可继续操作建议。
- AI 回答不得编造销量、平台排名、官方认证、交易额、确定性税务结论、法律结论或保证性收益。

## 报告解析、修改和版本管理

报告修改必须通过 proposal 和版本确认链路完成。

端到端流程：

```text
report version
  -> global chat parses report
  -> user asks for changes
  -> report_edit_proposals
  -> user preview and confirm
  -> new report_versions
  -> reports.current_version_id updated
```

报告解析：

- Report Parser 把报告拆成标题、章节、段落、指标、国家建议、风险提示、数据来源和附录。
- 聊天回答报告问题时应返回引用位置，例如章节标题、段落摘要或版本号。
- 报告解析结果只作为定位和解释辅助，不改变报告内容。

修改 proposal：

- `report_edit_proposals` 保存目标报告、目标版本、用户意图、建议修改内容、diff 或替换段落、风险提示、置信度和状态。
- proposal 状态建议为 `draft`、`pending_review`、`accepted`、`rejected`、`expired`。
- 生成 proposal 不得更新 `reports` 或 `report_versions` 正文。
- 用户可以拒绝 proposal、继续聊天要求调整 proposal，或确认保存新版本。

版本管理：

- `reports` 保存报告主记录和当前版本指针。
- `report_versions` 保存版本号、父版本、Markdown、HTML、来源类型、proposal ID、创建人或创建来源、创建时间和版本说明。
- 用户确认 proposal 后创建新 `report_versions`，并更新当前版本指针。
- 原版本必须保留，支持版本列表、版本预览和版本对比。
- 回滚策略后续任务再实现；本轮架构只要求确认后新增版本、不覆盖旧版本。

## 前端整体优化

前端优化围绕比赛演示主链路和真实用户效率展开。

优化方向：

- 信息架构：企业、产品、分析、报告和聊天入口统一，减少跳转断点。
- 移动端录入：企业拍照、商品多图上传、图片预览、删除、排序和重试适配手机。
- 市场选择：按后端返回区域分组、默认组合、禁用原因和搜索筛选展示国家。
- 全局聊天：固定入口、页面上下文感知、聊天历史、proposal 卡片和确认入口。
- 报告编辑：报告正文、proposal 预览、版本列表、版本对比和确认保存保持同一工作区。
- 空状态和错误状态：展示可执行下一步，例如补图、确认草稿、换国家、使用 fallback 或稍后重试。

前端边界：

- 不直接调用 Bailian 或第三方 API。
- 不保存 Key、Cookie、认证头或第三方凭据。
- 不写死目标国家、市场区域、provider 可用状态或默认组合。
- 不让聊天 UI 直接覆盖报告或绕过后端确认接口。

## 后续接口方向

Q40 只定义方向，后续 Q41-Q54 实现时再落地接口和迁移。

建议接口：

- `POST /api/product-intake/multi-image`：创建多图商品导入任务。
- `GET /api/product-intake/jobs/{id}`：读取导入任务、图片资产和草稿摘要。
- `PUT /api/product-intake/drafts/{id}`：保存人工编辑后的产品草稿。
- `POST /api/product-intake/drafts/{id}/confirm`：确认产品草稿入库。
- `POST /api/company-intake/photo`：创建企业拍照导入任务。
- `GET /api/company-intake/jobs/{id}`：读取企业导入任务和草稿摘要。
- `PUT /api/company-intake/drafts/{id}`：保存人工编辑后的企业草稿。
- `POST /api/company-intake/drafts/{id}/confirm`：确认企业草稿入库。
- `GET /api/target-markets/catalog`：返回区域、国家、默认组合和禁用原因。
- `POST /api/chat/sessions`、`POST /api/chat/sessions/{id}/messages`：创建聊天会话并发送消息。
- `POST /api/reports/{id}/proposals`：基于聊天或用户指令创建报告修改 proposal。
- `POST /api/reports/proposals/{id}/confirm`：确认 proposal 并保存新报告版本。
- `GET /api/reports/{id}/versions`：读取报告版本列表。

## 验收标准

- 多图商品录入生成 `product_drafts`，确认前不进入分析。
- 企业拍照录入生成 `company_drafts`，确认前不创建正式企业。
- 目标国家和市场区域从后端目录返回，前端没有硬编码国家列表。
- 全局聊天能解析报告和解释分析，但报告修改只生成 proposal。
- 用户确认 proposal 后生成新 `report_versions`，旧版本保留。
- 文档、日志、报告、聊天记录和状态文件不得写入 Key、Cookie、认证头、管理密码、完整敏感连接串或环境文件内容。
