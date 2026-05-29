# 智能商品导入规格

## 目标与范围

智能商品导入用于把用户主动提供的商品截图、企业产品目录截图、单个国内商品链接或手动文本整理成可编辑的产品草稿。系统先生成 `product_drafts`，用户确认后才写入正式 `products` 表，并进入既有市场分析、营销生成和报告生成流程。

支持的导入方式：

- 截图导入：用户上传淘宝、拼多多、京东商品详情页截图，或企业产品目录截图。
- 商品链接导入：用户粘贴淘宝、拼多多、京东的单个商品链接，系统尽力解析公开可访问页面基础信息。
- 手动文本导入：用户粘贴商品描述文本，系统按同一 AI 契约生成草稿。

明确不做：

- 不绕过登录、验证码、风控、签名校验、App 私有接口或平台访问限制。
- 不做列表页、搜索结果、店铺页、分页、后台定时或大规模商品采集。
- 不承诺能解析所有淘宝、拼多多、京东页面。
- 不把截图或链接解析结果表述为平台官方验证数据。

## 端到端流程

```text
User screenshot / URL / manual text
  -> Product Intake API
  -> product_import_jobs
  -> product_import_assets or domestic_product_links
  -> Qwen Product Understanding
  -> product_drafts
  -> Product Draft Review
  -> Confirm to Product
  -> existing analysis workflow
```

### 截图导入

1. 前端上传图片，并提示用户避免包含订单号、收货人、手机号、地址、聊天记录、账号头像等隐私信息。
2. 后端校验文件类型、大小、尺寸和存储路径，默认目录由 `PRODUCT_UPLOAD_DIR` 控制，单图大小由 `MAX_PRODUCT_IMAGE_SIZE_MB` 控制。
3. 后端创建 `product_import_jobs`，写入 `source_type=screenshot`，并保存 `product_import_assets` 元数据。
4. 后端调用 Qwen 视觉/多模态模型生成结构化 JSON。
5. JSON 校验通过后生成 `product_drafts`；低置信度草稿必须在前端突出提示。
6. 用户确认后创建正式 `products` 记录。

### 商品链接导入

1. 前端提交用户主动提供的单个 URL。
2. 后端校验 URL 只允许 `http`/`https`，禁止 `localhost`、内网 IP、云元数据地址、`file://` 等非公开目标；跟随重定向后也必须重新校验。
3. 后端识别 `taobao`、`pinduoduo`、`jd` 或 `unknown`，创建 `product_import_jobs` 和 `domestic_product_links`。
4. 如果 `ENABLE_DOMESTIC_URL_FETCH=false`，不发起真实页面请求，直接提示用户使用截图上传。
5. 如果启用链接解析，后端只读取公开可访问页面的基础文本，不使用 Cookie、账号密码、验证码服务、代理池或模拟登录。
6. 遇到登录墙、验证码、风控、访问受限、超时或页面结构不可解析时，`parse_status=fallback_required` 或 `failed`，并提示用户上传截图。
7. 成功解析到基础文本后，与平台识别结果一并交给 Qwen Product Understanding 生成草稿。

### 人工确认

- AI 提取结果必须先保存为 `product_drafts`。
- 用户可编辑草稿字段，包括产品名、品类、价格、规格、材质、颜色、卖点和目标用户。
- 用户确认后，后端基于确认后的草稿创建正式 `products` 记录，将草稿状态置为 `confirmed`，并写入 `confirmed_product_id`。
- 用户拒绝后，草稿状态置为 `rejected`，不得进入分析流程。
- 链接或截图中的平台标价默认仅作为 `product_drafts.price_cny` 参考值，不自动映射为正式产品采购成本。

## 计划 API

Q10 只定义接口方向，实际 API 在 Q11-Q13 实现。

- `POST /api/product-intake/screenshot`：创建截图导入任务，上传图片并触发视觉理解。
- `POST /api/product-intake/url`：创建单链接导入任务，执行安全 URL 校验和公开页面基础解析。
- `POST /api/product-intake/manual-text`：用用户粘贴文本创建导入任务并生成草稿。
- `GET /api/product-intake/jobs/{id}`：查询导入任务、资产、链接解析状态和草稿摘要。
- `PUT /api/product-intake/drafts/{id}`：保存用户编辑后的草稿字段。
- `POST /api/product-intake/drafts/{id}/confirm`：确认草稿并创建正式产品。
- `POST /api/product-intake/drafts/{id}/reject`：拒绝草稿。

所有接口错误响应必须脱敏，不返回密钥、Cookie、认证头、完整敏感 URL、整页 HTML、本地绝对路径或原始第三方异常。

## 数据模型设计

Q10 只写设计文档，不创建迁移。后续迁移建议命名为 `20260529_0006_create_product_intake_tables.py`，`down_revision="20260528_0005"`，沿用现有 SQLAlchemy 2.0 typed ORM、Integer 主键、`String` 状态字段、`JSON` 字段、`CreatedAtMixin`/`TimestampMixin` 和 Alembic 手写迁移风格。

### product_import_jobs

一次截图、链接或手动文本导入任务。

| 字段 | 类型建议 | 说明 |
| --- | --- | --- |
| `id` | Integer PK | 主键 |
| `company_id` | Integer FK `companies.id` | 企业，`ondelete=CASCADE`，加索引 |
| `source_type` | String(32) | `screenshot`、`url`、`manual_text` |
| `source_platform` | String(32) | `taobao`、`pinduoduo`、`jd`、`unknown` |
| `source_url` | String(2048), nullable | 用户提交 URL，不建议索引 |
| `status` | String(32) | `pending`、`processing`、`draft_ready`、`confirmed`、`failed` |
| `error_message` | Text, nullable | 脱敏失败原因 |
| `raw_text` | Text, nullable | 页面可见文本或手动文本摘要；不得保存隐私和整页 HTML |
| `model_used` | String(128), nullable | 使用的模型名 |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |

建议索引：`company_id`、`status`、`source_type`、`source_platform`、`created_at`、`(company_id, status)`。

### product_import_assets

导入任务关联的截图文件和元数据。

| 字段 | 类型建议 | 说明 |
| --- | --- | --- |
| `id` | Integer PK | 主键 |
| `import_job_id` | Integer FK `product_import_jobs.id` | 导入任务，`ondelete=CASCADE`，加索引 |
| `file_name` | String(255) | 脱敏后的文件名 |
| `file_path` | String(1024) | 存储路径，可加唯一约束；接口不回显本地绝对路径 |
| `mime_type` | String(128) | 允许的图片 MIME 类型 |
| `file_size` | Integer | 文件大小，单位 bytes |
| `width` | Integer, nullable | 图片宽度 |
| `height` | Integer, nullable | 图片高度 |
| `created_at` | DateTime | 创建时间 |

建议索引：`import_job_id`。

### product_drafts

AI 或解析流程生成的待确认产品草稿。多数业务字段允许为空，确认入库时再校验正式产品必填项。

| 字段 | 类型建议 | 说明 |
| --- | --- | --- |
| `id` | Integer PK | 主键 |
| `import_job_id` | Integer FK `product_import_jobs.id` | 导入任务，`ondelete=CASCADE`，加索引 |
| `company_id` | Integer FK `companies.id` | 企业，`ondelete=CASCADE`，加索引 |
| `product_name_cn` | String(255), nullable | 中文产品名 |
| `product_name_en` | String(255), nullable | 英文产品名 |
| `category` | String(128), nullable | 品类 |
| `price_cny` | Numeric(12,2), nullable | 平台标价或截图参考价，不等同采购成本 |
| `cost_price_cny` | Numeric(12,2), nullable | 用户确认后的采购成本 |
| `weight_kg` | Numeric(10,3), nullable | 重量 |
| `package_size` | String(128), nullable | 包装尺寸 |
| `material` | String(128), nullable | 材质 |
| `color_options` | JSON, nullable | 颜色选项 |
| `specification` | Text, nullable | 规格描述 |
| `selling_points` | JSON, nullable | 卖点数组或结构化卖点 |
| `target_users` | JSON, nullable | 目标用户 |
| `source_platform` | String(32), nullable | 来源平台识别 |
| `source_url` | String(2048), nullable | 用户提交 URL |
| `evidence` | JSON, nullable | 字段证据，保存最小必要摘录 |
| `confidence_score` | Numeric(5,4), nullable | 0 到 1，建议 CheckConstraint |
| `status` | String(32) | `draft`、`confirmed`、`rejected` |
| `confirmed_product_id` | Integer FK `products.id`, nullable | 确认后的正式产品，`ondelete=SET NULL`，加索引 |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |

建议索引：`company_id`、`import_job_id`、`status`、`confirmed_product_id`、`(company_id, status)`。

### domestic_product_links

用户主动提交的国内商品链接解析记录。

| 字段 | 类型建议 | 说明 |
| --- | --- | --- |
| `id` | Integer PK | 主键 |
| `import_job_id` | Integer FK `product_import_jobs.id` | 导入任务，`ondelete=CASCADE`，唯一索引 |
| `platform` | String(32) | `taobao`、`pinduoduo`、`jd`、`unknown` |
| `original_url` | String(2048) | 用户提交 URL |
| `normalized_url` | String(2048), nullable | 规范化 URL，不建议索引 |
| `item_id` | String(128), nullable | 可安全解析出的商品 ID，加索引 |
| `sku_id` | String(128), nullable | 可安全解析出的 SKU ID |
| `parse_status` | String(32) | `pending`、`parsing`、`parsed`、`fallback_required`、`failed` |
| `parsed_title` | String(512), nullable | 页面标题或商品标题 |
| `parsed_text` | Text, nullable | 最小必要页面可见文本，不保存整页 HTML |
| `parse_error` | Text, nullable | 脱敏解析失败原因 |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |

建议索引：`import_job_id` 唯一索引、`platform`、`parse_status`、`item_id`。

## Qwen 输出 JSON 契约

模型必须只返回一个 JSON object，不包 Markdown，不返回额外字段。未知字段使用 `""`、`null` 或 `[]`，不得编造销量、评价、认证、成交价、平台排名或官方验证结论。

```json
{
  "source_platform": "",
  "product_name_cn": "",
  "product_name_en": "",
  "category": "",
  "price_cny": null,
  "material": "",
  "specification": "",
  "dimensions": "",
  "weight_estimate": "",
  "color_options": [],
  "selling_points_cn": [],
  "selling_points_en": [],
  "target_users": [],
  "usage_scenarios": [],
  "cross_border_keywords_en": [],
  "risk_notes": [],
  "confidence_score": 0.0,
  "evidence": [
    {
      "field": "price_cny",
      "source": "screenshot_text",
      "value": ""
    }
  ]
}
```

字段规则：

- `source_platform` 仅表示识别到的来源线索，可为 `taobao`、`pinduoduo`、`jd`、`unknown`，不代表平台官方验证。
- `price_cny` 只表示截图或公开页面可见的标价/参考价，不代表成交价、采购成本或利润空间。
- `product_name_en`、`selling_points_en`、`cross_border_keywords_en` 可以由模型翻译或归纳，但必须作为草稿建议。
- `weight_estimate` 只有明确文本证据时写具体值；视觉估算必须在值或 `risk_notes` 中说明为估算。
- `risk_notes` 必须记录证据不足、规格不确定、价格不确定、认证/功效声明需复核、URL 解析受限、疑似隐私信息等风险。
- `confidence_score` 为 0 到 1 的整体置信度，基于商品识别完整度和关键字段证据强度。

证据规则：

- `evidence[].field` 必须对应顶层字段名，数组字段可用 `selling_points_cn[0]` 形式。
- `evidence[].source` 只允许 `screenshot_text`、`screenshot_visual`、`url_text`、`manual_text`、`model_inference`。
- 禁止使用 `official`、`platform_verified` 等证据来源。
- 关键字段有值时必须提供证据：`product_name_cn`、`price_cny`、`material`、`specification`、`dimensions`、`weight_estimate`、`color_options`、`selling_points_cn`。
- `value` 只保存短摘录或简短视觉描述，不保存整页 OCR、完整 HTML、完整敏感 URL、Cookie、账号、地址、手机号、订单号或聊天内容。

失败与低置信度策略：

- JSON 无法解析：记录 `AI_RESPONSE_PARSE_ERROR`，`product_import_jobs.status=failed`，不创建草稿。
- Schema 校验失败：记录 `AI_RESPONSE_SCHEMA_ERROR`，不创建草稿。
- `confidence_score < 0.35` 或 `product_name_cn` 为空：记录 `AI_PRODUCT_NOT_IDENTIFIED`，提示重新上传清晰截图或手动输入。
- `0.35 <= confidence_score < 0.65`：允许生成 `product_drafts.status=draft`，但前端必须展示低置信度警示，并要求人工逐项确认。
- `confidence_score >= 0.65`：生成普通草稿，但仍必须人工确认后才能入正式产品表。
- URL 安全解析失败、登录/验证码/风控阻断：记录 `URL_PARSE_BLOCKED` 或 `URL_PARSE_FAILED`，提示用户改用截图上传。

## 环境变量

新增变量只允许写入变量名、空值或本地占位值，不得写真实 Key。

```text
BAILIAN_VISION_MODEL=
BAILIAN_VISION_ENABLED=false
PRODUCT_UPLOAD_DIR=storage/product-intake
MAX_PRODUCT_IMAGE_SIZE_MB=10
ENABLE_DOMESTIC_URL_FETCH=false
```

默认建议：

- `BAILIAN_VISION_ENABLED=false`：未显式开启时不调用视觉/多模态模型。
- `ENABLE_DOMESTIC_URL_FETCH=false`：未显式开启时不发起国内商品页面请求，直接提示使用截图上传。
- `PRODUCT_UPLOAD_DIR=storage/product-intake`：只保存商品理解所需图片和元数据。
- `MAX_PRODUCT_IMAGE_SIZE_MB=10`：限制单张商品图片大小。

## 安全与合规

- 用户主动提供截图、链接或文本是唯一输入来源；系统不得主动发现、搜索或批量抓取商品页面。
- 链接解析仅用于单次商品理解，不做搜索结果、列表页、店铺页、分页或后台定时抓取。
- 不使用用户 Cookie、浏览器登录态、账号密码、验证码识别服务、模拟登录、代理池、Cookie 池或平台 App 私有接口。
- 遇到登录、验证码、风控、访问受限、反爬、超时或结构不可解析时，必须失败并提示上传截图。
- URL 抓取必须做 SSRF 防护：仅允许公开 `http`/`https` 目标，禁止内网、localhost、云元数据地址、`file://` 和非公开协议；重定向后也要重新校验。
- 上传截图前提示用户避免包含订单号、收货人、手机号、地址、聊天记录、账号头像等隐私信息。
- 只提取商品相关字段：名称、价格、规格、材质、颜色、卖点、目标用户、场景、关键词、证据和风险提示。
- 不保存买家身份、店铺后台信息、订单信息、聊天内容、收货信息、账号信息。
- 截图内容、页面文本、AI evidence、日志、报告和营销生成不得包含隐私信息、密钥、Token、Cookie、认证头或完整敏感连接串。
- 日志只记录平台、脱敏域名、解析状态、HTTP 状态码、耗时、错误类型和 `job_id`；不得记录完整带查询参数 URL、整页 HTML、完整 OCR 文本或本地绝对路径。
- Bailian/Qwen 视觉调用只能由后端完成；前端不得直接调用 Bailian 或持有任何 API Key。
- 管理和配置状态只能显示 `configured`、`not_configured`、`enabled`、`disabled` 等枚举，不显示密钥明文、掩码、长度或哈希。
