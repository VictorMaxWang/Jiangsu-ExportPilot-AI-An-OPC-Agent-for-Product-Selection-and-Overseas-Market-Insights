# Q33 Provider Timeout And Cache Optimization

- Task id: Q33
- Repo path: `D:\Desktop\苏品智航`
- Date: 2026-06-03
- Status: done

## Summary

- Optimized the default analysis flow without adding a fast mode, changing request payloads, or changing user entrypoints.
- Reduced external provider defaults to bounded HTTP timeouts: `7.0s` total and `3.0s` connect timeout for World Bank, GDELT, YouTube, Etsy, Etsy ping, and UN Comtrade.
- Kept all provider fallback behavior non-blocking and CSV-backed.

## Implementation

- Added shared backend provider timeout constants in `app.services.providers`.
- Updated UN Comtrade so the full yearly fetch attempt is bounded by one overall timeout instead of multiplying the timeout by year count.
- Preserved optional-key retry only for `401/403` auth responses; network failures, timeout, quota errors, invalid payloads, and empty responses fall back to `data/seed/trade_samples.csv`.
- Added safe UN Comtrade `fallback_reason` values: `provider_timeout` and `provider_unavailable`.
- Changed DataSourceService UN Comtrade caching to reuse by `hs_code + country + year_range`.
- Extended provider performance events to include safe `fallback_reason` and event-level `timeout_count`; fresh timeout fallbacks set `timeout=true`, while cache hits keep `timeout=false`.
- DataCollectionAgent now exposes UN Comtrade fallback reasons in the step output summary and step `fallback_reason`.

## Tests

- Added coverage for UN Comtrade timeout fallback and overall deadline behavior.
- Added coverage that same HS code, country, and year range cache hits do not call the provider again.
- Added coverage that provider failure remains workflow fallback, not workflow failed.
- Added coverage for provider event duration, timeout, fallback, and cache-hit fields.

## Validation

- `cd backend && py -3.11 -m pytest tests/test_un_comtrade_provider.py tests/test_data_source_service.py tests/test_analysis_workflow.py -q`: passed, `36 passed`.
- `cd backend && py -3.11 -m pytest tests -q`: passed, `294 passed`.
- `cd frontend && npm run lint`: passed, no ESLint warnings or errors.
- `cd frontend && npm run build`: passed, production build completed.

## Security Notes

- No API key values, cookies, request headers, `.env` contents, admin passwords, management passwords, or raw upstream payloads were logged or documented.
- Provider events record only safe labels, timings, status, fallback/cache/timeout flags, timeout count, country/year/auth mode, HTTP status, and safe fallback reason.
