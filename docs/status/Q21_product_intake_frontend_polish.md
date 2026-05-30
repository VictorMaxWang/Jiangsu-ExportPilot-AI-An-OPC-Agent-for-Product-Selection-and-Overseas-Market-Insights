# Q21 Product Intake Frontend Polish

- Task id: Q21
- Owner thread: Codex
- Start time: 2026-05-30 19:22:37 +08:00
- End time: 2026-05-30 19:38:15 +08:00
- Scope: `/products` entry point and `/products/import` user-facing intake flow

## Changed Paths

- `frontend/app/products/page.tsx`
- `frontend/app/products/import/_components/ProductImportWorkspace.tsx`
- `frontend/components/product-intake/ProductDraftEditor.tsx`
- `docs/status/Q21_product_intake_frontend_polish.md`

## Implementation Notes

- Made the `/products` "智能导入商品" entry more prominent with explanatory copy.
- Added the post-confirmation `/products?intake=confirmed` success notice: "已入库，可进入智能体分析".
- Updated `/products/import` tab text to "截图导入" and "商品链接导入".
- Kept screenshot intake fields visible: enterprise selection, platform selection, image upload, image preview, and "开始识别".
- Added always-visible status labels for "真实 Qwen 识别", "AI 回退草稿", and "需要人工处理".
- Improved link intake platform detection for Taobao short links (`e.tb.cn` / `tb.cn`), JD short links (`3.cn`), and Pinduoduo `yangkeduo.com` links.
- Made `needs_screenshot` show the exact prompt: "该平台页面可能需要登录或动态渲染，请上传商品截图继续分析".
- Kept failed link handling controlled by sanitizing technical stack-like error text before display.
- Renamed the safety section to "合规说明" and added the required boundaries: only user-provided screenshots/links, no bypassing login/CAPTCHA/risk controls, and no promise of real sales data.
- Made the draft evidence section visible as "证据 evidence" while preserving the editable evidence rows.

## Validation

- `npm run lint`: passed, no ESLint warnings or errors.
- `npm run build`: passed, production build completed successfully.
- Browser plugin connection was unavailable in this environment (`browser-client` was not trusted), so verification used local Playwright with installed Chrome.
- Local UI verification used a temporary mock API on `localhost:8100` and Next dev server on `127.0.0.1:3102`; both were stopped after verification.
- Verified visible UI checks:
  - `/products` shows "智能导入商品".
  - `/products?company_id=1&product_id=1&intake=confirmed` shows "已入库，可进入智能体分析".
  - `/products/import` shows both tabs, screenshot fields, compliance copy, and status labels.
  - Link tab shows the URL input placeholder and auto-detects Taobao short link, JD short link, and Pinduoduo link labels.

## Security Notes

- No backend key handling was changed.
- No keys, cookies, `.env` values, request headers, admin password, or credentials were printed or written.
- The temporary browser/mock validation used synthetic company/product data only.

## Blockers And Follow-Ups

- No implementation blockers.
- Production behavior still depends on the backend returning controlled `draft_ready`, `needs_screenshot`, or `failed` URL intake responses.
