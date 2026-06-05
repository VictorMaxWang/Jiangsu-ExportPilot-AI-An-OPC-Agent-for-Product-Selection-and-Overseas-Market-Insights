# Q43 Multi-Image Product Intake Frontend

## Task Info

- Task id: Q43
- Owner thread: Codex Q43 multi-image product intake frontend
- Start time: 2026-06-05 09:00:00 +08:00
- End time: 2026-06-05 09:47:23 +08:00

## Changed Paths

- `frontend/app/_lib/api-client.ts`
- `frontend/app/products/import/_components/ProductImportWorkspace.tsx`
- `frontend/components/product-intake/ProductDraftEditor.tsx`
- `frontend/tests/product-intake.spec.ts`
- `docs/status/Q43_multi_image_product_intake_frontend.md`

## Test Results

- `cd frontend && npm run lint`: passed with no ESLint warnings or errors.
- `cd frontend && npm run build`: passed; production build completed.
- `cd frontend && npm run test:e2e -- product-intake.spec.ts`: passed; 8 tests completed.
- Local render QA fallback: checked `http://127.0.0.1:3100/products/import` at 1280x900 and 375x812 with mocked company data. The heading and upload surface were visible, no page-level horizontal overflow was detected, and no console warnings/errors were emitted.

## Implementation Notes

- Borrowed Product Design workflow ideas only: brief-like upload guidance, audit checklist coverage, prototype-quality image manager behavior, and live surface QA.
- Did not copy Product Design connector configuration or plugin metadata.
- Screenshot import now supports click and drag/drop selection for up to 8 PNG, JPG, or WebP images.
- Each selected image displays a thumbnail, filename, size, MIME type, upload status, role, primary marker, and visible order.
- Users can delete images, move images up or down, set a primary image, and choose roles with button/select controls.
- Upload submits ordered multipart `files[]` and matching `image_roles[]` to `POST /api/product-intake/screenshots`.
- Result rendering shows returned assets, image count, primary image id, multi-image summary, draft details, and evidence provenance by image number and role.
- Draft save preserves evidence `image_index` and `image_role` fields.
- Draft editing now covers the core basic, physical, marketing, review, evidence, and rejection fields.
- The page remains Chinese by default and keeps the Chinese/EN switch through `useI18n()`.

## Blockers

- The in-app Browser plugin QA path was unavailable in this environment because the privileged native pipe bridge was not trusted. Regular Playwright QA was used as the fallback and passed.

## Follow-Up Notes

- Optional future polish: add pointer-based drag reordering on top of the current accessible up/down controls if reviewers ask for it.
