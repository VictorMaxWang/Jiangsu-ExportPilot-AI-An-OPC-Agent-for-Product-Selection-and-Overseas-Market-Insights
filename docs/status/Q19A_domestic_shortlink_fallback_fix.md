# Q19A Domestic Shortlink Fallback Fix

## Task Metadata

- Task id: Q19A
- Owner thread: Codex thread `019e77f0-c81a-76b0-99dd-cecd06b3f3ea`
- Start time: 2026-05-30T16:46:08+08:00
- End time: 2026-05-30T16:59:21+08:00
- Production target referenced: `https://opc.ankangyu.cn`
- Browser requirement: not used for Q19A; this task was backend/parser compatibility plus local validation.

## Changed Paths

- `backend/app/services/product_intake/domestic_url_parser.py`
- `backend/app/services/product_intake/domestic_page_fetcher.py`
- `backend/app/services/product_intake/url_intake.py`
- `backend/app/schemas/product_intake.py`
- `backend/tests/test_domestic_url_parser.py`
- `backend/tests/test_domestic_page_fetcher.py`
- `backend/tests/test_product_intake_url_api.py`
- `frontend/app/_lib/api-client.ts`
- `frontend/tests/product-intake.spec.ts`
- `docs/status/Q19A_domestic_shortlink_fallback_fix.md`

## Implementation Summary

- Added safe shortlink parse status for `e.tb.cn` and `3.cn`, mapped to `taobao` and `jd`.
- Allowed fetch validation for exact `e.tb.cn` and `3.cn` shortlink hosts while keeping final targets restricted to the domestic whitelist.
- Kept SSRF protections for non-http/https URLs, localhost, private network ranges, metadata IPs, userinfo URLs, and non-standard ports.
- Increased domestic page fetch redirect limit to 5 and total timeout to 10 seconds.
- Preserved the existing no-cookie/no-authorization fetch behavior and response size cap.
- Changed URL intake so shortlinks go through safe fetch/redirect handling instead of being rejected as unsupported domains.
- If a shortlink expands to a parsed product URL, the link record is updated with platform, normalized URL, item ID, and SKU ID before Qwen analysis.
- If shortlink expansion, page fetch, or HTML parsing fails, the API returns controlled `needs_screenshot` with `manual_required`, not HTTP 500.
- Added required URL intake response fields: `parse_status`, `source_platform`, `normalized_url`, `item_id`, and `sku_id`.

## Link Result Matrix

| Link type | Parser result | API fallback/result contract | Qwen draft generation | Empty draft behavior |
| --- | --- | --- | --- | --- |
| Taobao `e.tb.cn` shortlink | `source_platform=taobao`, `parse_status=shortlink` | Safe fetch follows up to 5 redirects; failed expansion returns `needs_screenshot` | Invoked only when public title/meta/visible text is parsed; test validates `model_used=qwen3.6-plus` and expanded Taobao normalized URL | No successful-looking blank draft; fallback draft is low confidence/manual required |
| Pinduoduo `mobile.yangkeduo.com/goods2.html?ps=...` | `source_platform=pinduoduo`, `parse_status=missing_item_id` | API returns `needs_screenshot`, not `unsupported_domain` and not 500 | Not invoked because no stable goods ID or parsed public page context exists | Low-confidence manual-required draft only |
| JD `3.cn` shortlink | `source_platform=jd`, `parse_status=shortlink` | Safe fetch follows allowed redirects; failed expansion returns `needs_screenshot` | Invoked only if public page text is parsed after redirect | No successful-looking blank draft; fallback draft is low confidence/manual required |

## Validation

- `py -3.11 -m pytest backend\tests\test_domestic_url_parser.py backend\tests\test_domestic_page_fetcher.py backend\tests\test_product_intake_url_api.py -q`
  - Result: `56 passed`
- `cd backend; py -3.11 -m pytest tests -q`
  - Result: `287 passed`
- `cd frontend; npm run lint`
  - Result: passed with no ESLint warnings or errors
- `cd frontend; npm run build`
  - Result: passed; Next.js production build completed

## Security Notes

- No platform login state, cookies, CAPTCHA bypass, or risk-control bypass was used.
- Fetcher still sends no `Cookie` or `Authorization` headers.
- Redirect validation runs before every request target.
- Response redaction preserves product IDs in normalized URLs while still redacting sensitive query keys such as token/secret/password/API key names.
- No API key, cookie, `.env`, admin password, request header, or upstream raw body was written to this file.

## Blockers And Follow-ups

- Q19 live in-app browser validation remains separately blocked by the Codex browser native bridge issue recorded in `docs/status/Q19_domestic_url_intake_live_validation.md`.
- After deployment, rerun Q19 live validation through `/products/import` to confirm production behavior for the three real links.
- If a platform changes shortlink redirect behavior or blocks public HTML, the expected controlled outcome is `needs_screenshot` with screenshot-upload guidance.
