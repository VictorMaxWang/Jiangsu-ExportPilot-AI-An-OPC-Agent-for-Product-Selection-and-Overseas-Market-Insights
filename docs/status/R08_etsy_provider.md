# R08 Etsy Provider

## Task

- Task id: R08
- Owner thread: Etsy Open API real integration Agent
- Start time: 2026-05-27 21:10:00 +08:00
- End time: 2026-05-27 21:42:46 +08:00

## Changed Paths

- `.env.example`
- `docker-compose.yml`
- `backend/app/core/config.py`
- `backend/app/schemas/market_data.py`
- `backend/app/schemas/__init__.py`
- `backend/app/services/providers/etsy.py`
- `backend/app/api/data.py`
- `backend/tests/test_etsy_provider.py`
- `backend/tests/test_data_provider_api.py`
- `docs/API_CAPABILITY_MATRIX.md`
- `docs/API_SOURCES.md`
- `docs/SECURITY.md`
- `docs/status/R08_etsy_provider.md`

## Summary

- Added backend-only Etsy settings: `ETSY_KEYSTRING`, `ETSY_SHARED_SECRET`, and `ENABLE_ETSY`.
- Added Etsy Open API v3 active listing search provider using `x-api-key` and no OAuth token.
- Added CSV fallback from `data/seed/competitor_samples.csv` for `Etsy` / `Etsy Sample` rows.
- Added `/api/data/etsy/search` and `/api/data/etsy/sync`.
- Added schema output compatible with `competitor_items` for downstream scoring.
- Removed runtime/deployment use of legacy `ETSY_API_KEY`; the backend does not read it.

## Test Results

- `C:\Users\12804\AppData\Local\Programs\Python\Python311\python.exe -m pytest backend/tests/test_etsy_provider.py backend/tests/test_data_provider_api.py`
  - Result: 28 passed
- `C:\Users\12804\AppData\Local\Programs\Python\Python311\python.exe -m pytest backend/tests`
  - Result: 70 passed
- Etsy `openapi-ping`
  - Result: skipped because `ETSY_KEYSTRING` and/or `ETSY_SHARED_SECRET` were not present in the current process environment.

## Security Notes

- No real API keys, key fragments, shared secrets, headers, or OAuth tokens were written to code, tests, docs, or status output.
- Etsy credentials are used only inside backend provider request headers.
- API responses expose only `api` / `csv_fallback` source markers and never include credential state or credential values.

## Blockers

- No implementation blockers.
- Live Etsy verification requires setting `ETSY_KEYSTRING` and `ETSY_SHARED_SECRET` in the backend runtime environment.

## Follow-up Notes

- When real Etsy env vars are available, rerun the official `openapi-ping` or a small listing search and record only the HTTP status/result.
- Consider adding a short-lived cache before repeated live Etsy syncs to reduce rate-limit pressure.
