# Q29 Product Intake Upload UI Fix

- Task id: Q29
- Owner thread: Codex product intake upload UI implementation
- Start time: 2026-05-31 21:13:56 +08:00
- End time: 2026-05-31 21:24:14 +08:00

## Changed Paths

- `frontend/app/_lib/api-client.ts`
- `frontend/app/products/import/_components/ProductImportWorkspace.tsx`
- `frontend/tests/product-intake.spec.ts`
- `docs/status/Q29_product_intake_upload_ui_fix.md`

## Summary

- 截图上传客户端固定使用 `POST /api/product-intake/screenshot`，并在 multipart `FormData` 中提交 `company_id`、`source_platform`、`file`。
- `/products/import` 截图上传过程中显示 loading，禁用相关输入，成功后展示 `draft_id`、`ai_result_type`、`model_used`、`confidence_score` 和草稿字段摘要。
- 截图上传失败时保留安全的后端业务提示；检测到 traceback、文件路径、源码行号或 stack trace 时改为非技术提示。
- 本任务未修改后端，也未对生产环境执行真实上传，避免创建新的生产草稿。

## Test Results

- `npm run lint`：通过。
- `npm run build`：通过。
- `npm run test:e2e -- tests/product-intake.spec.ts`：通过，6 passed。
- Backend tests：未运行，原因是本任务未改后端。

## Blockers

- 无。

## Follow-up Notes

- Q27 已验证生产后端截图接口可用；Q29 只覆盖前端上传体验和本地 mock Playwright 验证。
- 生产 Chrome 页面曾出现 DOM 读取超时，本任务未依赖生产浏览器上传验证。
