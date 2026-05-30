# Q19B Domestic URL Production API Validation

## Task Metadata

- Task id: Q19B
- Owner thread: Codex thread `019e77f0-c81a-76b0-99dd-cecd06b3f3ea`
- Start time: 2026-05-30T18:31:45+08:00
- End time: 2026-05-30T18:34:54+08:00
- Production base URL: `https://opc.ankangyu.cn`
- Validation mode: direct HTTPS production API calls; Codex in-app browser was not used.

## Changed Paths

- `docs/status/Q19B_domestic_url_production_api_validation.md`

## Safety Notes

- No Cookie, login session, Authorization header, platform login state, CAPTCHA bypass, or risk-control bypass was used.
- The provided reference product copy was not submitted to the production API and was used only as a manual comparison reference.
- No key, Cookie, `.env`, admin password, Authorization header, raw request headers, upstream raw bodies, or full database connection value is recorded here.

## Preflight

| Check | Method | HTTP | Result |
| --- | --- | ---: | --- |
| Backend health | `GET /health` | 200 | `status=ok`, `service=supinzhihang-backend` |
| Text smoke | `POST /api/ai/smoke/text` | 200 | `success=true`, `model=qwen3.6-plus`, `fallback_used=false` |
| Test company create | `POST /api/companies` | 201 | Created `E2E URL Intake Validation Company`, `company_id=3` |

## Production URL Intake Results

| Platform | Link | HTTP | Structured status | Parse/status fields | Qwen result | Draft/job | Confirmed into products | Contract result |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| Taobao | `https://e.tb.cn/h.Rg7IXlmjiRJ5ifv?tk=S71r5yDJd3y` | 422 | none | `detail.code=URL_HOST_NOT_ALLOWED`; no `status`, `parse_status`, `source_platform`, `normalized_url`, `item_id`, or `sku_id` in response | not invoked | none | N/A | Failed structured-status contract; production still rejects `e.tb.cn` as unsupported |
| Pinduoduo | `https://mobile.yangkeduo.com/goods2.html?ps=zheeHWNSNR` | 201 | `needs_screenshot` | Production response did not include new `parse_status/source_platform/normalized_url/item_id/sku_id` fields | `ai_result_type=manual_required`, `ai_fallback_used=false`, `model_used=null` | `job_id=1`, `draft_id=1`, low-confidence empty draft | N/A; not `draft_ready` | Controlled fallback, but exact dynamic-render prompt and new fields are missing in production response |
| JD | `https://3.cn/-2Q1WvH7?jkl=@X59VX7JUQ1@` | 422 | none | `detail.code=URL_HOST_NOT_ALLOWED`; no `status`, `parse_status`, `source_platform`, `normalized_url`, `item_id`, or `sku_id` in response | not invoked | none | N/A | Failed structured-status contract; production still rejects `3.cn` as unsupported |

## Prompt And Fallback Verification

- Required fallback prompt: `该平台页面可能需要登录或动态渲染，请上传商品截图继续分析`
- Taobao and JD did not reach fallback because production returned HTTP 422 `URL_HOST_NOT_ALLOWED`.
- Pinduoduo returned `needs_screenshot`, but API-visible `message/error_message` were `请上传截图继续分析`, not the required full dynamic-render prompt.
- No `draft_ready` response was observed, so no draft confirmation was attempted and no `/api/products` product visibility check was applicable.

## Findings

- Production AI text smoke is healthy with real `qwen3.6-plus`.
- Production appears not to include the Q19A shortlink/backend response-field fix yet:
  - `e.tb.cn` and `3.cn` still fail as `URL_HOST_NOT_ALLOWED`.
  - URL intake responses do not yet expose `parse_status`, `source_platform`, `normalized_url`, `item_id`, and `sku_id`.
- The Pinduoduo `goods2.html?ps=...` path is controlled and does not 500, but its API response still uses the shorter screenshot message.

## Local Validation

- `cd backend; py -3.11 -m pytest tests -q`
  - Result: `287 passed`
- `cd frontend; npm run lint`
  - Result: passed with no ESLint warnings or errors
- `cd frontend; npm run build`
  - Result: passed; Next.js production build completed

## Follow-ups

- Deploy the Q19A backend changes to production, then rerun this Q19B production API validation.
- After deployment, expected outcomes are:
  - Taobao/JD shortlink expansion failure returns controlled `needs_screenshot`, not 422.
  - Pinduoduo missing item context remains controlled `needs_screenshot`.
  - All URL intake responses expose the required structured fields.
  - If any response is `draft_ready`, confirm the draft and verify visibility through `/api/products?company_id=...`.
