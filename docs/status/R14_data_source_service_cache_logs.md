# R14 Unified Data Source Service, Cache, and Logs

- Task id: R14
- Owner thread: R14 unified data source service Agent
- Start time: 2026-05-28T09:40:00+08:00
- End time: 2026-05-28T10:05:51+08:00
- Status: done

## Completed Work

- Added unified `DataSourceService` for World Bank, GDELT, YouTube, Etsy, UN Comtrade, and CSV fallback orchestration.
- Added `data_source_caches` for 24-hour provider/endpoint/query/country cache without changing the existing `youtube_search_caches` table.
- Added `api_call_logs` for safe provider call logging with `success`, `fallback`, and `cache_hit` statuses.
- Added `/api/data-sources` routes for cache status, logs, competitor search, trend search, market profile, and trade data.
- Added unified response schemas for competitor and content trend results so CSV fallback can include non-Etsy and non-YouTube sample platforms without calling optional providers.
- Preserved existing `/api/data/*` provider routes and tests.

## Changed Paths

- `backend/alembic/versions/20260528_0003_create_data_source_cache_and_logs.py`
- `backend/app/api/data_sources/__init__.py`
- `backend/app/api/router.py`
- `backend/app/models/__init__.py`
- `backend/app/models/api_call_log.py`
- `backend/app/models/data_source_cache.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/data_sources.py`
- `backend/app/services/__init__.py`
- `backend/app/services/data_sources/__init__.py`
- `backend/app/services/data_sources/service.py`
- `backend/tests/test_data_source_service.py`
- `backend/tests/test_data_sources_api.py`
- `docs/status/R14_data_source_service_cache_logs.md`

## Test Results

```powershell
cd backend
py -3.11 -m compileall app
```

Result: passed.

```powershell
cd backend
py -3.11 -m pytest tests/test_data_source_service.py tests/test_data_sources_api.py -q
```

Result: passed, `12 passed`.

```powershell
cd backend
py -3.11 -m pytest tests -q
```

Result: passed, `120 passed`.

## Security Notes

- No real API keys, tokens, cookies, credentials, or secret values were added.
- API call logs store only sanitized logical provider information and normalized query parameters.
- Error messages written by `DataSourceService` are fixed safe summaries and do not include upstream URLs, headers, keys, tokens, or raw exception strings.
- eBay, Rakuten, and Reddit are not imported, instantiated, called, logged, or cached by R14.

## Blockers

- None.

## Follow-up Notes

- The old `YoutubeSearchCacheService` and `youtube_search_caches` table remain for compatibility with existing `/api/data/youtube/*` behavior.
- `ENABLE_OPTIONAL_PROVIDERS` is intentionally not implemented in R14 because no eBay, Rakuten, or Reddit provider clients exist yet.
- `data/seed/*` remains the unified CSV fallback source.
