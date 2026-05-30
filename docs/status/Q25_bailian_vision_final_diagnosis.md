# Q25 Bailian Vision Final Diagnosis

## Task Info

- Task id: Q25
- Owner thread: Q25 Bailian vision final diagnosis agent
- Start time: 2026-05-30 14:55:00 +08:00
- End time: 2026-05-30 15:02:57 +08:00

## Changed Paths

- `backend/app/api/ai.py`
- `backend/app/services/ai/bailian_client.py`
- `backend/tests/test_ai_integration.py`
- `scripts/probe_bailian_vision.py`
- `docs/status/Q25_bailian_vision_final_diagnosis.md`

## Final Diagnosis

- Text smoke is currently successful in production: `model=qwen3.6-plus`, `success=true`, `fallback_used=false`.
- Vision smoke is not currently production-usable: production returned `model=qwen-vl-plus`, `success=false`, `sanitized_error=BAILIAN_UPSTREAM_ERROR`, `error_stage=upstream_http`, `upstream_status_code=400`.
- Code diagnosis: the OpenAI-compatible request shape in `BailianClient.vision_chat()` is correct for Qwen-VL image input: chat completions with user `content` containing `type=text` and `type=image_url`, where `image_url.url` is a Base64 Data URL.
- Root-cause finding: the previous smoke image was `4x4`, while Alibaba Cloud Bailian vision documentation requires image width and height both greater than `10px`. This is a request-format/input-validation problem and is sufficient to explain the current `400`.
- The configured model ID is still external configuration via `BAILIAN_VISION_MODEL`. `qwen-vl-plus` is listed in Alibaba Cloud's OpenAI-compatible Qwen-VL model list, but this thread could not prove account-level availability because the local shell has no `DASHSCOPE_API_KEY` and no real probe was sent from local.
- Screenshot import remains safe: it only returns `real_qwen` after a real vision call succeeds and the response parses into a valid product understanding result. Vision call, parse, schema, disabled, or missing-model failures continue to create a `fallback` or `manual_required` draft.

## Official References

- OpenAI-compatible Qwen-VL supports `image_url` image input and lists Qwen-VL model IDs including `qwen-vl-plus`: https://help.aliyun.com/zh/model-studio/qwen-vl-compatible-with-openai
- OpenAI-compatible chat parameters allow `image_url.url` to be an image URL or Base64 Data URL: https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions
- Vision documentation shows DashScope native multimodal `{image,text}` format and requires image width and height to be greater than `10px`: https://help.aliyun.com/zh/model-studio/vision

## Probe Results

- Local safe probe: `scripts/probe_bailian_vision.py` was run without reading `.env`; local shell reported `DASHSCOPE_API_KEY` missing, so no real Bailian request was sent. Output was limited to `model`, `method`, `success`, `status_code`, `sanitized_error`, and `suggested_action`.
- Production text smoke, one call only: `success=true`, `model=qwen3.6-plus`, no sanitized error.
- Production vision smoke, one call only: `success=false`, `model=qwen-vl-plus`, `upstream_status_code=400`. This is the pre-Q25 deployed behavior and still uses the old invalid `4x4` smoke image until Q25 is deployed.

## Implementation Notes

- Updated the vision smoke image to `32x32` PNG so it satisfies the documented minimum image size.
- Added safe upstream code extraction in the Bailian client. Only status code and a constrained upstream error code are retained for diagnostics; no raw upstream body, request body, headers, or credential material is recorded.
- Added `scripts/probe_bailian_vision.py` to compare OpenAI-compatible `image_url` against DashScope native multimodal. The script reads only `DASHSCOPE_API_KEY`, `BAILIAN_VISION_MODEL`, and `BAILIAN_BASE_URL`, sends at most two requests, and emits only safe JSON fields.
- `/api/ai/smoke/vision` now gives more specific actions for invalid input/format, model unavailable, account/model permission, OpenAI-compatible unsupported method, and DashScope native multimodal fallback.

## User Console Checklist

- In Alibaba Cloud Bailian / DashScope console, confirm the server-side `DASHSCOPE_API_KEY` belongs to the intended region and workspace.
- Confirm the workspace can invoke the model configured in `BAILIAN_VISION_MODEL`.
- If `qwen-vl-plus` remains unavailable after the 32x32 smoke fix, choose a currently authorized vision model in the console and update only the environment variable value, then restart the backend.
- If OpenAI-compatible fails but native multimodal succeeds, route backend vision calls through DashScope native multimodal for that configured model.

## Validation

- `cd backend && py -3.11 -m pytest tests/test_ai_integration.py -q`: passed, 27 passed.
- `cd backend && py -3.11 -m pytest tests -q`: passed, 279 passed.
- `cd frontend && npm run lint`: passed, no ESLint warnings or errors.
- `cd frontend && npm run build`: passed, Next.js production build completed.

## Security Notes

- No `.env`, API key, token, secret, cookie, admin password, or credential file was read or output.
- Real smoke/probe records include only model, method/provider, success, fallback flag, sanitized error code, error stage, upstream status code, and suggested action.
- No request headers, raw upstream response bodies, raw uploaded images, or raw prompt bodies are stored in this status file.
