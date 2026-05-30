# Q24 Bailian Vision Smoke Diagnosis

## Task Info

- Task id: Q24
- Owner thread: Q24 Bailian vision diagnosis agent
- Start time: 2026-05-30 13:20:00 +08:00
- End time: 2026-05-30 13:47:54 +08:00
- GitHub issue: https://github.com/VictorMaxWang/Jiangsu-ExportPilot-AI-An-OPC-Agent-for-Product-Selection-and-Overseas-Market-Insights/issues/3

## Changes

- Extended AI smoke responses with safe diagnostic fields: `error_stage`, `upstream_status_code`, and `suggested_action`.
- Kept Bailian vision model configurable through `BAILIAN_VISION_MODEL`; no fallback model or silent model switching was added.
- Kept the OpenAI-compatible multimodal request format unchanged: `/chat/completions` with `image_url` and a `data:image/png;base64,...` URL.
- Tightened vision smoke success validation so the response must confirm both `ok=true` and `image_seen=true`.
- Hardened screenshot import fallback for vision call, parse, and schema failures with `ai_result_type="fallback"`, `ai_fallback_used=true`, low confidence, and the user-facing message: `视觉模型未通过生产验收，请先上传截图后人工补全或配置可用视觉模型。`
- Added frontend API types for the expanded AI smoke/status response shape.

## Changed Paths

- `backend/app/api/ai.py`
- `backend/app/schemas/ai.py`
- `backend/app/schemas/__init__.py`
- `backend/app/services/ai/bailian_client.py`
- `backend/app/services/product_intake/screenshot_analyzer.py`
- `backend/tests/test_ai_integration.py`
- `backend/tests/test_product_intake_screenshot_api.py`
- `frontend/app/_lib/api-client.ts`
- `docs/status/Q24_bailian_vision_diagnosis.md`

## Production Diagnosis

Current production state before this Q24 deployment:

| Probe | Provider | Model | Configured | Success | Fallback used | Sanitized error | Error stage | Upstream status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `GET /api/ai/status` | `bailian` | `qwen3.6-plus` | true | false | false | null | null | null |
| status text | `bailian` | `qwen3.6-plus` | true | false | false | null | null | null |
| status vision | `bailian` | `qwen-vl-plus` | true | false | false | null | null | null |
| `POST /api/ai/smoke/text` | `bailian` | `qwen3.6-plus` | true | true | false | null | null | null |
| `POST /api/ai/smoke/vision` | `bailian` | `qwen-vl-plus` | true | false | false | `BAILIAN_UPSTREAM_ERROR` | null | null |

Production text smoke is working. Production vision smoke reaches the configured model name `qwen-vl-plus` but fails upstream. The deployed production build does not yet include the new Q24 diagnostic fields, so `error_stage`, `upstream_status_code`, and `suggested_action` are expected to appear after this branch is deployed.

## Validation

- `cd backend && py -3.11 -m pytest tests/test_ai_integration.py tests/test_product_intake_screenshot_api.py -q`: passed, 42 passed.
- `cd backend && py -3.11 -m pytest tests -q`: passed, 275 passed.
- `cd frontend && npm run lint`: passed, no ESLint warnings or errors.
- `cd frontend && npm run build`: passed, Next.js production build completed.

## Security Notes

- No `.env`, API key, token, Authorization header, database URL, admin password, or backup credential file was read or output.
- Smoke results record only provider, model, configured, success, fallback flag, sanitized error, error stage, upstream status code, and whether a suggested action exists.
- No request body, request headers, or raw upstream response body is stored in this status file.

## Follow-up

- Blocker: production must deploy this branch before the new diagnostic fields can appear on `https://opc.ankangyu.cn/api/ai/smoke/vision`.
- Deploy this Q24 branch to production.
- Rerun `POST /api/ai/smoke/vision`; if it still fails, use the new safe diagnostics to check whether `BAILIAN_VISION_MODEL` is a valid Bailian Qwen-VL model ID for the current account and region.
- If `qwen-vl-plus` is not available for the production account/region, configure a valid model ID in the server `.env` or deployment secret store, restart the backend, and rerun vision smoke.
