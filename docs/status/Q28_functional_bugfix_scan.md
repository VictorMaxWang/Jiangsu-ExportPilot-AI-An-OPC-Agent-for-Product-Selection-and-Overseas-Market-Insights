# Q28 Functional Bugfix Scan

- Task id: Q28
- Owner thread: Codex main thread
- Start time: 2026-06-28 13:30 +08:00
- End time: 2026-06-28 14:24 +08:00

## Summary

Implemented the Q28 functional bugfix batch only. Security hardening items remain deferred as follow-up notes.

## Changed Paths

- `backend/Dockerfile`
- `backend/app/core/config.py`
- `backend/app/schemas/data_sources.py`
- `backend/app/schemas/products.py`
- `backend/app/services/scoring/opportunity_scoring.py`
- `backend/tests/test_ai_integration.py`
- `backend/tests/test_data_sources_api.py`
- `backend/tests/test_database_api.py`
- `backend/tests/test_opportunity_scoring_api.py`
- `frontend/app/_components/LanguageProvider.tsx`
- `frontend/app/admin/_components/ProviderStatusDashboard.tsx`
- `frontend/app/dashboard/_components/DashboardDetailWorkspace.tsx`
- `frontend/app/reports/_components/ReportDetailWorkspace.tsx`
- `frontend/tests/company-intake.spec.ts`
- `frontend/tests/resilience.spec.ts`

## Fixes

- Bailian settings now resolve `DASHSCOPE_API_KEY` first, then `BAILIAN_API_KEY`, then the `SUPIN_` variants.
- Admin provider status UI now recovers from a runtime 401 by showing the password panel even when the static build was not produced with production `APP_ENV`.
- Backend Docker image now pre-creates both product and company intake storage directories.
- Data-source competitor and trend search schemas now accept ISO-3 country codes.
- Product create/update schemas now reject blank Chinese names and negative cost, weight, and MOQ values.
- Opportunity scoring rejects mixed valid/invalid `product_ids` instead of silently scoring the subset.
- Dashboard and report detail pages guard state cleanup for aborted stale requests.
- `LanguageProvider` tolerates blocked `localStorage` reads/writes.
- Stabilized an existing company-intake e2e CTA assertion by checking the link `href` before navigating to it.

## Test Results

- Pre-fix backend regression check: 11 failed, 38 passed, confirming the target bugs.
- Pre-fix frontend resilience spec: 4 failed, confirming the target bugs.
- Backend targeted: `C:\Users\12804\AppData\Local\Programs\Python\Python311\python.exe -m pytest backend\tests\test_ai_integration.py backend\tests\test_opportunity_scoring_api.py backend\tests\test_data_sources_api.py -q` -> 36 passed.
- Backend product validation: `C:\Users\12804\AppData\Local\Programs\Python\Python311\python.exe -m pytest backend\tests -q -k product` -> 89 passed, 278 deselected.
- Backend full suite: `C:\Users\12804\AppData\Local\Programs\Python\Python311\python.exe -m pytest backend\tests -q` -> 367 passed.
- Backend post-cleanup spot check: `C:\Users\12804\AppData\Local\Programs\Python\Python311\python.exe -m pytest backend\tests\test_opportunity_scoring_api.py -q` -> 3 passed.
- Frontend targeted: `npm run test:e2e -- resilience.spec.ts` -> 4 passed.
- Frontend lint: `npm run lint` -> passed with no warnings or errors.
- Frontend build: `npm run build` -> passed.
- Frontend full e2e: `npm run test:e2e` -> 18 passed.

## Blockers

- None.

## Notes

- A first build/e2e attempt was run concurrently and failed because `next build` and the Playwright dev server both used `.next`. The commands were rerun serially and passed.
- A first full e2e attempt exposed an existing company-intake CTA navigation flake under concurrent load. The test now asserts the CTA `href` and navigates to the verified target.

## Deferred Security Follow-Up

- Review public report and data-source status/log endpoints for production authorization requirements.
- Add CSRF/rate-limit hardening for admin actions if the admin surface expands beyond the current password header model.
- Sanitize or otherwise constrain persisted report HTML before rendering it in the browser.
- Keep API keys and provider configuration display limited to configured/not configured states; no plaintext secret exposure was added in Q28.
