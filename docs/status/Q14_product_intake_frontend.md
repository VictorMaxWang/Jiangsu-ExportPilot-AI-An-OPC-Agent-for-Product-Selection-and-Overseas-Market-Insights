# Q14 智能商品导入前端

## 任务信息

- 任务编号：Q14
- 任务名称：智能商品导入前端
- 负责线程：Q14 前端智能导入页面 Agent
- 开始时间：2026-05-29 18:20:00 +08:00
- 完成时间：2026-05-29 19:08:48 +08:00

## 修改路径

- `backend/app/schemas/product_intake.py`
- `backend/app/services/product_intake/draft_review.py`
- `backend/tests/test_product_intake_draft_api.py`
- `frontend/app/_components/FallbackNotice.tsx`
- `frontend/app/_lib/api-client.ts`
- `frontend/app/products/page.tsx`
- `frontend/app/products/_components/ProductsWorkspace.tsx`
- `frontend/app/products/import/`
- `frontend/components/product-intake/`
- `docs/status/Q14_product_intake_frontend.md`

## 完成内容

- 新增 `/products/import` 智能商品导入页面，包含截图导入和链接导入两个 Tab。
- 新增截图导入企业选择、平台选择、本地图片预览、识别状态展示和草稿编辑入口。
- 新增链接导入企业选择、商品链接输入、前端平台识别提示、`needs_screenshot` 回退提示和截图导入切换入口。
- 新增 `ProductDraftEditor`，支持编辑草稿字段、置信度和 evidence，支持保存、确认入库和拒绝草稿。
- 扩展前端 API client，新增 product-intake 类型与截图、URL、草稿、确认、拒绝请求方法。
- 扩展后端草稿更新接口，允许保存 `confidence_score` 和 `evidence`，并补充清洗校验测试。
- 在 `/products` 页面增加“智能导入商品”入口，并支持确认入库后的 `company_id`、`product_id` 深链选中。

## 验证命令与结果

- `py -3.11 -m pytest tests/test_product_intake_draft_api.py -q`：通过，8 passed。
- `py -3.11 -m pytest tests/test_product_intake_screenshot_api.py -q`：通过，10 passed。
- `py -3.11 -m pytest tests/test_product_intake_url_api.py -q`：通过，8 passed。
- `npx tsc --noEmit`（`frontend/`）：通过。
- `npm run lint`（`frontend/`）：通过，无 ESLint warnings or errors。
- `npm run build`（`frontend/`）：通过，包含 `/products/import` 路由构建。
- 浏览器验证：`http://127.0.0.1:3004/products/import` 可加载企业；京东链接提交后显示指定 `needs_screenshot` 提示；草稿可编辑保存；确认后跳转到 `/products?company_id=1&product_id=1`，产品列表展示并选中新产品。
- 截图上传接口验证：使用真实 PNG 调用 `POST /api/product-intake/screenshot` 成功返回 `draft_ready_with_low_confidence`、`next_action=manual_fill` 和草稿 ID。

## 安全结果

- 前端不直接调用 Bailian，不读取或展示任何第三方 API Key。
- 截图上传使用用户主动选择的本地文件，预览只使用浏览器本地 object URL。
- 页面明确提示仅分析用户主动提供的截图/链接、链接失败请上传截图、人工确认后入库、不承诺获取平台真实销量。
- URL 回退状态不展示完整 HTML、Cookie、认证头或平台登录态信息。

## Blockers 与 Follow-up

- Blockers：无代码阻塞。自动化文件上传受 Codex in-app browser 能力限制，未能自动注入本地文件；Chrome 验证环境被本机扩展拦截 localhost API。截图上传接口已通过真实 PNG 请求验证。
- Follow-up：如需完整手工验收，可在普通浏览器打开 `/products/import`，选择 PNG/JPEG/WebP 截图确认本地预览视觉效果。
