# Q27 Real Product Screenshot Validation

## Task Info

- Task id: Q27
- Owner thread: Codex Q27 real product screenshot validation agent
- Start time: 2026-05-31T19:17:00+08:00
- End time: 2026-05-31T20:02:24+08:00
- Production URL: `https://opc.ankangyu.cn`
- Target company: `#8` `E2E Screenshot Smoke Company 2`
- Changed paths: `docs/status/Q27_real_product_screenshot_validation.md`

## Summary

Used Chrome to open the provided Taobao, Pinduoduo, and JD product links. No login, CAPTCHA, risk-control, cookie, account, order, address, phone, or secret data was bypassed or recorded.

At least one real product screenshot produced a valid `product_draft` and was confirmed into the product table:

- Confirmed draft: `product_drafts.id=14`
- Import job: `product_import_jobs.id=14`
- Confirmed product: `products.id=6`
- AI result: `ai_result_type=real_qwen`, `model_used=qwen-vl-plus`, `confidence_score=0.9000`

## Production Preflight

| Check | Result |
| --- | --- |
| `GET /health` | OK, service `supinzhihang-backend` |
| `POST /api/ai/smoke/text` | success, `model=qwen3.6-plus`, `fallback_used=false` |
| `POST /api/ai/smoke/vision` | success, `model=qwen-vl-plus`, `fallback_used=false` |
| `GET /api/companies` | company `#8` exists |

## Chrome Capture Results

| Platform | Chrome result | Safe screenshot result | Upload result |
| --- | --- | --- | --- |
| Taobao | Short link opened in Chrome and resolved to a visible Taobao product page for a Nantong bedding item. Query parameters were not recorded. | Captured only the visible product region below the browser/address bar, including product image, title/price/spec area, and no private buyer/account data. | Uploaded successfully; generated and confirmed draft `#14`. |
| Pinduoduo | Link opened in Chrome and resolved to `mobile.yangkeduo.com/goods2.html` with query parameters redacted from notes. | Blocked for validation: the tab became unresponsive to Chrome DOM/screenshot inspection, and no privacy-safe product crop could be verified. | Not uploaded. |
| JD | Short link opened in Chrome and resolved to a visible mobile JD product image page for a UNIQLO clothing item. Query parameters were not recorded. | Captured only the visible product hero image area below the browser/address bar, with no account/order/address/phone data. | Uploaded successfully but returned a fallback draft `#15` due AI parse failure; not confirmed. |

## Upload And Draft Evidence

Chrome UI upload attempts on `/products/import` were attempted first, including file chooser and page-origin upload attempts from the import page. In this Codex Chrome session those attempts timed out and produced no new production draft. To complete the validation, the same Chrome-captured cropped screenshots were uploaded to the production screenshot endpoint. This validates the production screenshot import API, storage, Qwen vision call, draft persistence, and confirmation path, but the UI file-upload interaction itself remains a tooling blocker for this run.

### Taobao Screenshot

- Upload endpoint result: HTTP 201
- `import_job_id`: `14`
- `draft_id`: `14`
- `job_status`: `draft_ready`, later `confirmed`
- `draft_status`: `draft`, later `confirmed`
- `ai_result_type`: `real_qwen`
- `ai_fallback_used`: `false`
- `model_used`: `qwen-vl-plus`
- `confidence_score`: `0.9000`
- `product_name_cn`: `四季通用床品套件`
- `category`: `床上用品`
- `price_cny`: `138.64`
- `material`: `棉`
- `specification`: `1.2米床三件套`
- `color_options`: `浅蓝色`
- `selling_points_cn`: `四季通用`, `官方立减15%省26元`, `预计明天发货`, `15天价保`
- `selling_points_en`: `Four-season universal`, `Official discount: Save ¥26 with 15% off`, `Estimated delivery tomorrow`, `15-day price protection`
- `evidence`:
  - `product_name_cn / screenshot_text`: `四季通用床品套件`
  - `price_cny / screenshot_text`: `券后 ¥138.64`
  - `material / screenshot_visual`: `棉`
  - `specification / screenshot_text`: `1.2米床三件套`
  - `color_options / screenshot_visual`: `浅蓝色`
- Confirmation: `POST /api/product-intake/drafts/14/confirm` succeeded with `company_id=8`
- Persistence verification:
  - `GET /api/product-intake/drafts/14`: `status=confirmed`, `confirmed_product_id=6`
  - `GET /api/product-intake/jobs/14`: `status=confirmed`, `model_used=qwen-vl-plus`
  - `GET /api/products/6`: product exists with `product_name_cn=四季通用床品套件`

### JD Screenshot

- Upload endpoint result: HTTP 201
- `import_job_id`: `15`
- `draft_id`: `15`
- `job_status`: `draft_ready_with_low_confidence`
- `draft_status`: `draft`
- `ai_result_type`: `fallback`
- `ai_fallback_used`: `true`
- `model_used`: `qwen-vl-plus`
- `confidence_score`: `0.0000`
- `product_name_cn`: null
- `category`: null
- `selling_points`: empty arrays, with risk note `视觉模型未通过生产验收，请先上传截图后人工补全或配置可用视觉模型。`
- `evidence`: empty
- `error_code`: `AI_RESPONSE_PARSE_ERROR`
- Confirmation: not performed, because Taobao draft `#14` already satisfied the real-screenshot draft and persistence requirement.

## Test Results

- `cd backend && py -3.11 -m pytest tests -q`: passed, `288 passed in 30.15s`
- `cd frontend && npm run lint`: passed, no ESLint warnings or errors
- `cd frontend && npm run build`: passed, Next.js production build completed

## Blockers And Notes

- Chrome successfully opened the marketplace links and produced safe visible crops for Taobao and JD.
- Pinduoduo could not be safely captured because the Chrome tab became unresponsive to DOM/screenshot inspection; no bypass was attempted.
- Chrome UI upload on `/products/import` timed out in this Codex session and did not create a draft. Direct endpoint upload was used for the production validation evidence.
- Temporary screenshot files were kept outside the repository and were not committed.
- No API keys, cookies, admin passwords, `.env` values, Authorization headers, raw upstream bodies, or private browser/session data were recorded.
