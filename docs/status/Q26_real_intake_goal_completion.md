# Q26 Real Intake Production Completion

- Task id: Q26
- Owner thread: Codex Q26 completion closeout agent
- Start time: 2026-05-31T18:45:09+08:00
- End time: 2026-05-31T18:45:24+08:00
- Status: complete

## Scope

Record final production closeout for the real product intake goal at `https://opc.ankangyu.cn`.
The user manually completed production deployment and verified latest `main` is online.
No OrcaTerm deployment was attempted in this closeout.

## Changed Paths

- `docs/status/Q26_real_intake_goal_completion.md`

The earlier blocker record is intentionally retained at
`docs/status/Q26_real_intake_goal_blocked.md`.

## Production Deployment

- Deployed commit: `8aa1aff` (`Q26 update screenshot upload blocker evidence`)
- Production URL: `https://opc.ankangyu.cn`
- Runtime health: backend, frontend, PostgreSQL, and Redis were reported healthy.
- `/health` returned normally.

## Production Verification

- Qwen text smoke passed: `/api/ai/smoke/text` returned `success=true`, model `qwen3.6-plus`.
- Qwen vision smoke passed: `/api/ai/smoke/vision` returned `success=true`, model `qwen-vl-plus`.
- Screenshot upload fix passed: `POST /api/product-intake/screenshot` returned HTTP `201`, no longer HTTP `500`, and no longer `UPLOAD_STORAGE_UNAVAILABLE`.
- Backend container storage `/app/storage/product-intake` was verified writable; write test returned `ok`.
- Screenshot upload invoked Qwen vision and returned `model_used=qwen-vl-plus`.
- A solid-color 32x32 test image returned `ai_result_type=manual_required`, `ai_fallback_used=false`, `model_used=qwen-vl-plus`, and `error_code=AI_PRODUCT_NOT_IDENTIFIED`. This is expected because the test image is not a product image.

## Prior Intake And Flow Evidence

The previous production validation evidence remains documented in
`docs/status/Q26_real_intake_goal_blocked.md`.

- URL intake was previously verified for Taobao, Pinduoduo, and JD with no HTTP `500`.
- Taobao and Pinduoduo returned controlled `needs_screenshot` results.
- JD returned `manual_required` or another controlled result.
- Existing production verification records: product id `5`, analysis id `3`, report id `5`.
- Dashboard, marketing, and reports pages were verified open.
- Report `5` was checked and no real sales, GMV, guaranteed sales, or similar unsupported claims were found.

## Test Results

- `cd backend && py -3.11 -m pytest tests -q`: passed, `288 passed`.
- `cd frontend && npm run lint`: passed, no ESLint warnings or errors.
- `cd frontend && npm run build`: passed.

## Remaining Limits

- Real商品截图仍需人工或浏览器进一步验证，当前纯色图只能证明接口、存储和 Qwen vision 调用链路正常。
- 淘宝、拼多多、京东平台如遇登录、验证码或风控限制，应继续返回或引导 `needs_screenshot`，不要把该场景伪装成抓取成功。
- 本收尾文件只记录用户已完成的生产部署和验证结果，不新增或编造生产数据。

## Security Notes

- 本文件未记录 API Key、Cookie、`.env`、管理密码、数据库连接串或 Authorization header。
- 第三方密钥仍应只通过后端环境变量或部署密钥配置读取。

## Follow-up Notes

- Q26 production closure is complete based on the deployed commit and verification results listed above.
- Future enhancement work should use a real product screenshot to validate商品识别质量，而不是复用纯色测试图作为质量判断。
