# Q48 Company Photo Intake Frontend

- Task id: Q48
- Owner thread: Codex Q48 company photo intake frontend
- Start time: 2026-06-05 18:08:00 +08:00
- End time: 2026-06-05 18:59:21 +08:00
- Status: done

## Summary

Implemented the frontend for photo-based quick company creation. `/companies` now links to a localized photo intake flow, `/companies/import` supports mobile camera upload and multi-image preview, and users can review/edit a company draft before confirming it into `companies`.

Product Design was borrowed only as workflow method: brief discipline, mobile upload ergonomics, visible state QA, and responsive review. No plugin code, assets, connector config, `.app.json`, scripts, templates, or workspace bindings were copied.

## Changed Paths

- `frontend/app/_lib/api-client.ts`
- `frontend/app/companies/page.tsx`
- `frontend/app/companies/_components/CompaniesWorkspace.tsx`
- `frontend/app/companies/import/page.tsx`
- `frontend/app/companies/import/_components/CompanyImportWorkspace.tsx`
- `frontend/components/company-intake/CompanyDraftEditor.tsx`
- `frontend/tests/company-intake.spec.ts`
- `docs/status/Q48_company_photo_intake_frontend.md`

## Test Results

| Command | Result |
| --- | --- |
| `cd frontend && npm run lint` | Passed with no ESLint warnings or errors. |
| `cd frontend && npm run build` | Passed; production build completed and `/companies/import` was generated. |
| `cd frontend && npm run test:e2e -- company-intake.spec.ts` | Passed: 6 tests completed. |

## Implementation Notes

- Added typed company-intake frontend API helpers for `POST /api/company-intake/photo`, draft fetch/update, confirm, and reject.
- `/companies` now supports `company_id` and `intake=confirmed` query state, selects the confirmed company, and shows a localized success banner.
- `/companies/import` supports up to 4 PNG/JPG/WebP images, separate phone camera input with `capture="environment"`, multi-file selection, drag/drop, preview, ordering, deletion, image roles, upload status, result metadata, assets, draft preview, and evidence.
- The draft editor exposes only the required fields: company name, region, industry, description, main products, target-market suggestions, confidence, and evidence.
- The privacy warning tells users not to upload private or sensitive document numbers and notes that recognized sensitive text is redacted by the backend.

## QA Notes

- Playwright mocked the backend API and verified multipart order, `image_roles[]`, evidence image provenance, draft update payloads, confirm redirect, and mobile viewport overflow.
- In-app Browser/IAB direct navigation tooling was not exposed in this session, so Playwright Chromium was used as the browser QA fallback.

## Blockers

- None.

## Follow-up Notes

- Optional future polish: add pointer-drag image reordering if reviewers ask for it; current up/down controls are accessible and covered by tests.
