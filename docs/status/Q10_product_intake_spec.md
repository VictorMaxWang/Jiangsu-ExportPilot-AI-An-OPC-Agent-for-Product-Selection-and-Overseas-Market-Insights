# Q10 智能商品导入需求重排与数据模型设计

## 任务信息

- 任务编号：Q10
- 任务名称：智能商品导入需求重排与数据模型设计
- 负责人线程：Q10 智能商品导入需求重排与数据模型设计 Agent
- 开始时间：2026-05-29 14:50:16 +08:00
- 完成时间：2026-05-29 14:52:29 +08:00

## 修改路径

- `.env.example`
- `docs/PROJECT_BRIEF.md`
- `docs/ARCHITECTURE.md`
- `docs/TASK_BOARD.md`
- `docs/SECURITY.md`
- `docs/PRODUCT_INTAKE_SPEC.md`
- `docs/status/Q10_product_intake_spec.md`

## 完成内容

- 将智能商品导入加入项目核心能力，覆盖截图导入、单个商品链接导入、Qwen 视觉/多模态商品理解、产品草稿和人工确认入库。
- 在架构文档中新增 Product Intake 模块，明确 Screenshot Intake、URL Intake、Qwen Product Understanding、Product Draft Review、Confirm to Product 的边界。
- 在任务板中将 Q10 记录为已完成，并追加 Q11-Q16 后续任务；未改动 Q02-Q08 的既有 `not_started` 状态。
- 新增 `docs/PRODUCT_INTAKE_SPEC.md`，写明导入流程、计划 API、四张数据表设计、AI JSON 契约、环境变量和安全合规边界。
- 在 `.env.example` 和 `docs/SECURITY.md` 中加入新增环境变量名和默认占位值。

## 数据模型设计结论

- Q10 仅完成设计，不创建迁移、不新增 SQLAlchemy 模型、不改运行时代码。
- 后续建议在 Q13 创建迁移 `20260529_0006_create_product_intake_tables.py`，`down_revision="20260528_0005"`。
- 设计表包括 `product_import_jobs`、`product_import_assets`、`product_drafts`、`domestic_product_links`。
- AI 结果必须先进入 `product_drafts`；用户确认后才写入正式 `products`。

## 验证命令与结果

- `git diff --check`：通过。仅出现 Windows 工作区换行提示，无空白错误。
- `rg -n "Q10|Q11|Q12|Q13|Q14|Q15|Q16|截图导入|商品链接导入|失败|回退|人工确认|合规|BAILIAN_VISION_MODEL|BAILIAN_VISION_ENABLED|PRODUCT_UPLOAD_DIR|MAX_PRODUCT_IMAGE_SIZE_MB|ENABLE_DOMESTIC_URL_FETCH|confidence_score|evidence|screenshot_text|url_text|model_inference|product_import_jobs|product_import_assets|product_drafts|domestic_product_links" docs/PRODUCT_INTAKE_SPEC.md docs/TASK_BOARD.md .env.example docs/SECURITY.md -S`：通过，关键规格、任务和变量均已覆盖。
- `git diff -- .env.example docs | rg -n "DASHSCOPE_API_KEY=.{8,}|BAILIAN_API_KEY=.{8,}|YOUTUBE_DATA_API_KEY=.{8,}|ETSY_KEYSTRING=.{8,}|UN_COMTRADE_API_KEY=.{8,}|EBAY_CLIENT_SECRET=.{8,}|REDDIT_CLIENT_SECRET=.{8,}|Bearer [A-Za-z0-9]|Cookie:|Authorization:"`：未命中真实凭据、Cookie 或认证头形态。
- 未运行后端/前端测试：本任务只改文档和环境变量示例，不改运行时代码。

## 环境变量

本任务新增变量名和占位默认值：

```text
BAILIAN_VISION_MODEL=
BAILIAN_VISION_ENABLED=false
PRODUCT_UPLOAD_DIR=storage/product-intake
MAX_PRODUCT_IMAGE_SIZE_MB=10
ENABLE_DOMESTIC_URL_FETCH=false
```

未写入任何真实 Key、Token、Secret、Cookie、认证头或敏感连接串。

## 安全策略影响

- 影响安全策略：是。
- 已在 `docs/PRODUCT_INTAKE_SPEC.md` 和 `docs/SECURITY.md` 写明不绕过登录/验证码/风控、不批量采集、不抓取用户隐私、失败回退截图上传、结果需人工确认。
- 已明确截图和链接解析结果只能作为用户提供材料和 AI/页面可见信息提取，不得表述为平台官方验证数据。

## Blockers 与 Follow-up

- Blockers：无。
- Follow-up：Q02-Q08 在任务板中仍为 `not_started`，但 `docs/status/` 已存在 Q02-Q06 状态文件；按 Q10 计划本次不修正该历史状态漂移。
- Follow-up：Q11-Q13 实施时需要补后端模型、迁移、服务、API 和测试；Q14-Q16 负责前端、流程接入、部署和演示材料。
