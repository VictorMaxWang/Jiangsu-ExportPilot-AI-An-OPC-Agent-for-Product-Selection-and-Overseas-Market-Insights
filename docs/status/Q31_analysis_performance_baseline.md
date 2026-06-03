# Q31 Analysis Performance Baseline

- Task id: Q31
- Owner thread: Codex analysis performance instrumentation
- Start time: 2026-06-03 16:30:00 +08:00
- End time: 2026-06-03 17:15:00 +08:00
- Status: done

## Summary

- Added safe performance instrumentation plan for `analysis/run` without changing agent order, provider order, cache behavior, fallback behavior, or business outputs.
- Baseline target shape: 1 product, `US/JP/GB`, `competitor_limit=20`.
- Selection rule: first company, first product. Production data was not seeded or modified outside starting the requested analysis run.

## Local Baseline

- Test time: 2026-06-03 16:36:21 +08:00
- Environment: local FastAPI app via `TestClient`.
- Note: local DB had company `1` but no products, so seed products were imported locally with the existing `/api/products/import` endpoint before the baseline run.
- Request: `company_id=1`, `product_ids=[1]`, `target_countries=["US","JP","GB"]`, `competitor_limit=20`
- Analysis id: `1`
- Workflow status: `fallback_used`
- Wall elapsed: `25178 ms`
- Recorded workflow duration: `25101 ms`
- Counts: provider `52`, Qwen `13`, timeout `0`, cache hit `21`, fallback `43`
- Slowest step: `03_data_collection` / `DataCollectionAgent`, `24317 ms`, provider calls `31`, fallback `15`

### Local Provider Hot Spots

| Provider | Endpoint | Calls | Total ms | Max ms | Cache hits | Fallbacks | Timeouts | Statuses |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| un_comtrade | trade_data | 9 | 17932 | 8148 | 6 | 9 | 0 | cache_hit, fallback |
| un_comtrade | trade_data_http | 10 | 17599 | 3821 | 0 | 0 | 0 | error, success |
| worldbank | market_profile | 9 | 5947 | 2347 | 6 | 0 | 0 | cache_hit, success |
| worldbank | market_profile_http | 3 | 5846 | 2289 | 0 | 0 | 0 | success |
| data_source_service | content_trends | 9 | 200 | 75 | 6 | 9 | 0 | cache_hit, fallback |
| gdelt | search_news_trends | 3 | 67 | 26 | 0 | 3 | 0 | fallback |
| etsy | search_competitors | 6 | 40 | 14 | 3 | 6 | 0 | cache_hit, fallback |
| youtube | search_video_trends | 3 | 39 | 22 | 0 | 3 | 0 | fallback |

### Local Qwen Hot Spots

| Model | Operation | Calls | Total ms | Max ms | Fallbacks | Timeouts | Statuses |
|---|---:|---:|---:|---:|---:|---:|---|
| qwen3.6-plus | chat | 13 | 0 | 0 | 13 | 0 | error |

## Production Baseline Attempt

- Test time: 2026-06-03 16:37:30 +08:00
- Environment: `https://opc.ankangyu.cn`
- Request: `company_id=1`, `product_ids=[7]`, `target_countries=["US","JP","GB"]`, `competitor_limit=20`
- Analysis id: `5`
- Poll duration: `904208 ms`
- Observed status after polling: `running`
- Current step after polling: `09_report_prep`
- `GET /api/analysis/5/performance`: `404`

## Findings

- Local instrumentation shows `03_data_collection` dominates elapsed time for the requested shape.
- Local provider aggregation shows UN Comtrade dominates provider time, and raw `trade_data_http` yearly calls make the total visible.
- Production still did not finish within 15 minutes and reached `09_report_prep`; the new performance endpoint is not available on production yet, so production provider/Qwen breakdown cannot be read until this implementation is deployed.

## Test Results

- `cd backend && py -3.11 -m pytest tests -q`: passed, `291 passed`.
- `cd frontend && npm run lint`: passed, no ESLint warnings or errors.
- `cd frontend && npm run build`: passed.

## Security Notes

- No API key values, cookies, request headers, environment file contents, management passwords, prompts, or raw upstream request payloads were recorded in this document.
- Performance events expose only bounded safe fields such as provider, endpoint label, country, year, auth mode, status, duration, fallback, cache hit, and timeout.
