# Q22 Real Product E2E Validation

- Task id: Q22
- Owner thread: Codex
- Start time: 2026-05-30 19:41:34 +08:00
- End time: 2026-05-30 20:18:00 +08:00
- Environment: production `https://opc.ankangyu.cn`
- Changed paths: `docs/status/Q22_real_product_e2e_validation.md`

## Scope

Validate the live chain for domestic product intake:

`link/screenshot intake -> draft -> product -> analysis/run -> dashboard -> marketing -> report`

Target company created in production:

- Company name: E2E 智能导入测试企业
- Company id: 4
- Region: 江苏南通
- Industry: 家纺/服饰测试
- Target countries: US, JP, GB

## Security Notes

- No API keys, cookies, `.env` values, admin passwords, request headers, or raw upstream secret-bearing bodies were recorded.
- No platform login, CAPTCHA, risk-control bypass, cookie reuse, proxy bypass, or batch crawling was used.
- Public platform screenshots were captured from unauthenticated pages only.
- Domestic marketplace source links were used only for validation and product text comparison.

## Browser Availability

- Codex in-app browser was attempted twice through the Browser plugin.
- Result: unavailable. The browser runtime reported that the privileged native bridge was not available/trusted.
- Because the requested in-app browser could not be connected, UI browser assertions are recorded as blocked. Production API and HTTP page-open checks were still recorded for validation evidence.

## Preflight

| Check | Result |
| --- | --- |
| `GET /health` | HTTP 200, service reported ok |
| `GET /products/import` | HTTP 200 |
| `GET /api/companies` | HTTP 200 |
| Branch merge precheck | `git branch --no-merged main --all` returned no unmerged branches |

## Product Link Results

| Platform | Input link | API/UI result | Fields observed | Fallback reason | Qwen draft generated | Confirmed product | `/products` visible |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Taobao | `https://e.tb.cn/h.Rg7IXlmjiRJ5ifv?tk=S71r5yDJd3y` | HTTP 422 validation failure, not HTTP 500 | `code=URL_HOST_NOT_ALLOWED`, message says host is not supported | Short-link host `e.tb.cn` is not accepted by production URL intake | No | No | No |
| Pinduoduo | `https://mobile.yangkeduo.com/goods2.html?ps=zheeHWNSNR` | `needs_screenshot`, HTTP 200 | `job_id=3`, `draft_id=3`, `ai_result_type=manual_required`, `ai_fallback_used=false`, `model_used=null`, `error_code=URL_PARSE_FAILED`, message `请上传截图继续分析` | Public page redirected to login; screenshot continuation attempted | No | No | No |
| JD | `https://3.cn/-2Q1WvH7?jkl=@X59VX7JUQ1@` | HTTP 422 validation failure, not HTTP 500 | `code=URL_HOST_NOT_ALLOWED`, message says host is not supported | Short-link host `3.cn` is not accepted by production URL intake | No for the short link | Yes, via manual workaround from public visible text | Yes |

Additional JD follow-up without bypass:

- The public JD short link resolved in an unauthenticated browser to an item page with visible title text for the provided product.
- The resolved JD item URL was submitted to URL intake and returned `needs_screenshot`, HTTP 201.
- Observed fields: `job_id=4`, `draft_id=4`, `status=needs_screenshot`, `ai_result_type=manual_required`, `ai_fallback_used=false`, `model_used=qwen3.6-plus`, `error_code=AI_PRODUCT_NOT_IDENTIFIED`.
- This did not produce a real Qwen product draft; it produced a manual-required draft.

## Screenshot Fallback

| Screenshot source | Endpoint result | Notes |
| --- | --- | --- |
| Pinduoduo public page screenshot | HTTP 500 `Internal Server Error` | Public page was a login page. Screenshot continuation was attempted and blocked by production 500. |
| JD public full-page PNG screenshot | HTTP 500 `Internal Server Error` | Public page contained product-visible text. |
| JD viewport JPEG screenshot | HTTP 500 `Internal Server Error` | Retried with smaller JPEG; production still returned 500. |

Required fallback prompt status:

- Backend API message for `needs_screenshot`: `请上传截图继续分析`.
- Frontend source contains the required full prompt: `该平台页面可能需要登录或动态渲染，请上传商品截图继续分析`.
- In-app browser visual verification of that prompt was blocked by the Browser plugin connection failure.

## Draft And Product Confirmation

Because production screenshot intake returned HTTP 500, the chain could not continue through the intended screenshot-import path. To validate the downstream analysis/report chain, draft 4 was manually updated using only unauthenticated JD public visible text:

- Product id: 4
- Product name CN: 优衣库男装修身无褶长裤/休闲裤 482876 32深米色 79/170/78A
- Product name EN: UNIQLO Men Slim Fit Flat Front Pants 482876 Beige
- Category: 男装休闲裤
- Confirm result: HTTP 200
- Product API `GET /api/products/4`: HTTP 200
- Product page `GET /products?company_id=4&product_id=4`: HTTP 200

This confirmation is a downstream validation workaround, not proof that screenshot intake succeeded.

## Analysis Run

Analysis was run with the confirmed product:

- Request: product id 4, target countries US, JP, GB
- Analysis id: 2
- Final status: `fallback_used`
- Current step: `09_report_prep`
- Top country: US
- Top score: 51.43
- Scoring items: 3
- Used providers: `bailian`, `csv_seed`, `data_source_service`, `etsy`, `un_comtrade`, `worldbank`
- Fallback providers: `bailian`, `data_source_service`, `etsy`, `un_comtrade`
- Error message: null

## Page And API Checks

| Check | Result |
| --- | --- |
| `GET /dashboard/2` | HTTP 200 |
| `GET /api/dashboard/2` | HTTP 200, 3 product scores, 3 price ranges, 3 recommendations |
| `GET /marketing?analysis_id=2` | HTTP 200 |
| `POST /api/marketing/generate` | HTTP 504 `BAILIAN_TIMEOUT` after about 92 seconds |
| `GET /reports?analysis_id=2` | HTTP 200 |
| `POST /api/reports/generate` | HTTP 200, report id 3 |
| `GET /reports/3` | HTTP 200 |

## Report Claim Audit

Audited report id 3 for prohibited affirmative claims:

| Term | Count | Review |
| --- | ---: | --- |
| 真实销量 | 3 | All matches were negative disclaimers such as "不代表真实销量" or "不声明真实销量". |
| 平台成交额 | 0 | No match. |
| GMV | 0 | No match. |
| 保证销量 | 0 | No match. |

Conclusion: no affirmative claim of real sales, platform transaction amount, GMV, or guaranteed sales was found in the generated report. The report uses fallback and evidence-limitation disclaimers.

## Validation Findings

1. Taobao and JD short links return HTTP 422 `URL_HOST_NOT_ALLOWED` instead of a structured `draft_ready`, `needs_screenshot`, or `failed` status object. This is controlled and not HTTP 500, but it does not satisfy the structured-status contract.
2. Pinduoduo URL intake correctly returns `needs_screenshot`, but screenshot upload returns HTTP 500 in production.
3. JD resolved item URL can reach a `needs_screenshot` response with `model_used=qwen3.6-plus`, but no Qwen product draft is generated; the result remains `manual_required`.
4. Screenshot fallback is blocked by production HTTP 500 for both Pinduoduo and JD screenshots.
5. Marketing page opens, but standalone marketing generation timed out with `BAILIAN_TIMEOUT`.
6. Report generation succeeds and the generated report avoids prohibited affirmative sales/GMV claims.

## Follow-ups

- Add production support for accepted short-link hosts or normalize/resolve `e.tb.cn` and `3.cn` into supported canonical domains without bypassing platform controls.
- Ensure unsupported domestic links return structured `failed` or `needs_screenshot` responses instead of HTTP 422 when the UI contract requires no unstructured result.
- Fix production screenshot intake HTTP 500 and return controlled `needs_screenshot` or draft results.
- Re-run Codex in-app browser UI validation once the Browser plugin bridge is available.
- Investigate Bailian timeout behavior for `POST /api/marketing/generate`.
