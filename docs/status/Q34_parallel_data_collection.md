# Q34 Parallel Data Collection

- Task id: Q34
- Repo path: `D:\Desktop\苏品智航`
- Date: 2026-06-03
- Status: done

## Summary

- Optimized the default `DataCollectionAgent`; no fast mode or alternate workflow was added.
- Replaced product-country serial data collection with bounded async concurrency.
- Added per-run de-duplication for repeated `keyword + country` competitor/content calls and `hs_code + country` trade calls.
- Preserved existing `raw_signals` and `data_collection_summary` state structures for dashboard, scoring, and report consumers.

## Implementation

- Added configurable `DATA_COLLECTION_CONCURRENCY` / `SUPIN_DATA_COLLECTION_CONCURRENCY`, default `3`, bounded to `1..8`.
- Data collection now builds unique market, competitor, content, and trade jobs, executes them through one `asyncio.Semaphore`, and reassembles results in the original product-country order.
- Same-country market profile requests remain one call per country.
- Duplicate in-run provider requests are served from local task results and recorded as non-provider-counting cache-hit performance events.
- Leaked provider task exceptions are converted into compatible fallback response objects and recorded with safe `provider_unavailable` or `provider_timeout` reasons.
- Step summaries now include `provider_call_count`, `cache_hit_count`, `fallback_count`, `timeout_count`, `concurrency`, and `local_cache_hit_count`.

## Changed Paths

- `.env.example`
- `backend/app/core/config.py`
- `backend/app/services/analysis_performance.py`
- `backend/app/services/agents/export_insight_workflow.py`
- `backend/tests/test_analysis_workflow.py`
- `docs/status/Q34_parallel_data_collection.md`

## Tests

- Added coverage that parallel data collection preserves the serial result shape.
- Added coverage that duplicate competitor/content/trade keys call providers once and record local cache hits.
- Added coverage that a single provider failure falls back without failing the data collection step.
- Added coverage that bounded concurrency materially reduces runtime with slow mock providers.

## Validation

- `cd backend && py -3.11 -m pytest tests/test_analysis_workflow.py -q`: passed, `8 passed`.
- `cd backend && py -3.11 -m pytest -q`: passed, `298 passed`.
- `cd frontend && npm run lint`: passed, no ESLint warnings or errors.
- `cd frontend && npm run build`: passed, production build completed.

## Security Notes

- No API keys, cookies, headers, `.env` values, or raw upstream payloads were read or documented.
- New performance events record only safe provider labels, endpoint labels, timing, status, cache/fallback/timeout flags, country, and fallback reason.
