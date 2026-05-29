# Q12 国内商品链接解析后端

## 任务信息

- 任务编号：Q12
- 任务名称：国内商品链接解析后端
- 负责线程：Q12 国内商品链接解析后端 Agent
- 开始时间：2026-05-29 15:45:00 +08:00
- 完成时间：2026-05-29 16:10:00 +08:00

## 修改路径

- `backend/alembic/versions/20260529_0007_create_domestic_product_links.py`
- `backend/app/models/product_intake.py`
- `backend/app/models/__init__.py`
- `backend/app/schemas/product_intake.py`
- `backend/app/schemas/__init__.py`
- `backend/app/services/ai/prompts.py`
- `backend/app/services/product_intake/domestic_url_parser.py`
- `backend/app/services/product_intake/domestic_page_fetcher.py`
- `backend/app/services/product_intake/url_intake.py`
- `backend/app/services/product_intake/screenshot_analyzer.py`
- `backend/app/services/product_intake/__init__.py`
- `backend/app/api/product_intake/__init__.py`
- `backend/tests/test_domestic_url_parser.py`
- `backend/tests/test_product_intake_url_api.py`
- `docs/status/Q12_domestic_product_url_intake.md`

## 完成内容

- 新增 `POST /api/product-intake/url`，支持用户主动提交单个淘宝、天猫、京东、拼多多/yangkeduo 商品链接。
- 新增 `domestic_product_links` ORM 和迁移，保存链接平台、规范化 URL、商品 ID/SKU ID、解析状态、页面标题、脱敏可见文本和脱敏错误码。
- 新增国内商品 URL 解析器，限制 `http/https`、白名单域名、安全端口和明显内网/metadata 目标，并提取平台商品 ID。
- 新增页面抓取器，使用 `httpx` 手动限制重定向、超时、响应大小和 DNS 公网校验，不使用 Cookie、登录态、验证码处理或浏览器自动化。
- 页面解析仅提取 `title`、`meta description`、`og:title`、`og:image`、最多 6000 字符可见文本、价格候选和商品名候选。
- 登录页、验证码页、风控页、空内容、抓取失败和配置关闭时均返回 `needs_screenshot`，提示 `请上传截图继续分析`。
- 新增 URL 文本理解 Qwen prompt，要求只使用后端抽取的 URL 元数据和可见文本，不编造销量、评价、排名、认证或平台官方验证。
- Qwen 成功时创建待确认 `product_drafts`；低置信度、抓取失败或 AI 不可用时创建低置信度空草稿以保持人工流程可继续。

## 验证命令与结果

- `py -3.11 -m pytest backend/tests/test_product_intake_screenshot_api.py -q`：通过，10 passed。
- `py -3.11 -m pytest backend/tests/test_domestic_url_parser.py backend/tests/test_product_intake_url_api.py -q`：通过，25 passed。
- `py -3.11 -m pytest backend/tests/test_product_intake_screenshot_api.py backend/tests/test_ai_integration.py backend/tests/test_domestic_url_parser.py backend/tests/test_product_intake_url_api.py -q`：通过，50 passed。
- `py -3.11 -m pytest backend/tests -q`：通过，220 passed。
- `py -3.11 -m alembic -c alembic.ini upgrade head`：通过，已运行到 `20260529_0007`。
- `git diff --check`：通过，仅有 Windows 工作区换行提示，无空白错误。

## 安全结果

- 未写入真实 API Key、Token、Cookie、认证头或用户凭据。
- URL 抓取默认受 `ENABLE_DOMESTIC_URL_FETCH=false` 控制，未显式开启时不会发起真实页面请求。
- 请求头只包含最小公开头，不传 Cookie、Authorization、用户登录态或平台私有头。
- API 响应和 job detail 不返回原始 URL、整页 HTML、`raw_text`、Cookie、认证头或页面完整文本。
- 页面抓取遇到登录、验证码、风控、访问受限、超时、非 HTML 或响应过大时统一要求上传截图继续分析。

## Blockers 与 Follow-up

- Blockers：无。
- Follow-up：后续 Q13 可在现有 `product_drafts` 基础上实现草稿编辑、确认入正式产品和拒绝流程。
