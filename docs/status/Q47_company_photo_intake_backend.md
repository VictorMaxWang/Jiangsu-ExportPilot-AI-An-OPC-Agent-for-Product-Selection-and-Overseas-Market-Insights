# Q47 Company Photo Intake Backend

- Task id: Q47
- Owner thread: Codex Q47 company photo intake backend
- Start time: 2026-06-05 16:30:00 +08:00
- End time: 2026-06-05 16:40:35 +08:00
- Status: done

## Summary

Implemented backend-only company photo intake. Users can upload 1-4 company images, receive a sanitized `company_drafts` record with image-level evidence, edit/reject the draft, and confirm it into `companies`.

## Changed Paths

- `.env.example`
- `backend/alembic/versions/20260605_0009_q47_company_photo_intake.py`
- `backend/app/api/router.py`
- `backend/app/api/company_intake/__init__.py`
- `backend/app/core/config.py`
- `backend/app/models/company_intake.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/company_intake.py`
- `backend/app/services/__init__.py`
- `backend/app/services/ai/prompts.py`
- `backend/app/services/company_intake/__init__.py`
- `backend/app/services/company_intake/photo_analyzer.py`
- `backend/app/services/company_intake/draft_review.py`
- `backend/tests/test_company_intake_photo_api.py`
- `backend/tests/test_company_intake_draft_api.py`

## Verification

| Command | Result |
| --- | --- |
| `py -3.11 -m compileall app` | Passed |
| `py -3.11 -m pytest tests\test_company_intake_photo_api.py tests\test_company_intake_draft_api.py -q` | Passed: 19 passed |
| `py -3.11 -m pytest tests -q` | Passed: 348 passed |
| Temp SQLite `py -3.11 -m alembic upgrade head` | Passed: migration chain reached `20260605_0009` |

## Privacy Notes

- Full local image paths are not returned by API schemas.
- `CompanyImportJob.raw_text` is not populated with OCR text or raw model output.
- Phone numbers, ID card numbers, full unified social credit codes, emails, long account-like numbers, local paths, tokens, cookies, and secrets are redacted from AI fields, evidence, draft updates, reject reasons, error messages, API responses, and persisted draft JSON.
- Confirmed companies store only normal company fields and target country recommendations; `main_products` stays on the draft and is preserved in the generated company description.

## Blockers

- None.

## Follow-up Notes

- Frontend upload/review UI remains out of scope for this backend task.
- The company photo flow reuses the existing Bailian vision configuration via `BAILIAN_VISION_ENABLED` and `BAILIAN_VISION_MODEL`.
