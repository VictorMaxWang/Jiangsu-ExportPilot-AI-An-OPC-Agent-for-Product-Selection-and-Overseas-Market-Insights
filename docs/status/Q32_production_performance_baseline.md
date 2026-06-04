# Q32 Production Performance Baseline

- Task id: Q32
- Production target: `https://opc.ankangyu.cn`
- Repo path: `D:\Desktop\[Chinese workspace folder]`
- Test time: 2026-06-03 19:08-19:28 +08:00
- Status: production baseline collected; validation passed

## Deployment And Route Confirmation

- Local branch: `main`
- Local `HEAD`: `6d95a3c8772ddf80b78efb1b97093bbb6e47cab5`
- Local `origin/main`: `6d95a3c8772ddf80b78efb1b97093bbb6e47cab5`
- Remote `refs/heads/main`: `6d95a3c8772ddf80b78efb1b97093bbb6e47cab5`
- Commit subject: `Add analysis performance instrumentation`
- Working tree before Q32 doc: clean.
- Production does not expose `/version` or `/api/version`, so the exact production commit hash could not be read from the site.
- Production Q31 deployment status: deployed/observable by route and schema. `GET /api/analysis/__codex_nonexistent__/performance` returned `422` path int parsing, `GET /api/analysis/0/performance` returned `404` with `Analysis run not found`, and the real run returned a Q31 performance payload with `steps`, `provider_summary`, `qwen_summary`, `events`, and `truncated_event_count`.

## Production Smoke

| Check | Result | Safe details |
|---|---:|---|
| `GET /health` | 200 | `status=ok`, `service=supinzhihang-backend` |
| `POST /api/ai/smoke/text` | 200 | `provider=bailian`, `model=qwen3.6-plus`, `configured=true`, `success=true`, `fallback_used=false`, `sanitized_error=null` |
| `POST /api/ai/smoke/vision` | 200 | `provider=bailian`, `model=qwen-vl-plus`, `configured=true`, `success=true`, `fallback_used=false`, `sanitized_error=null` |

## Baseline Run

- Request: `company_id=1`, `product_ids=[7]`, `target_countries=["US","JP","GB"]`, `competitor_limit=20`
- Analysis id: `6`
- Started at: `2026-06-03T11:10:53.427420Z`
- Finished at: `2026-06-03T11:27:50.779206Z`
- Final status: `fallback_used`
- Current/final step: `09_report_prep`
- Next page: `/reports?analysis_id=6`
- Performance duration: `1017352 ms`
- Counts: provider `33`, Qwen `13`, timeout `10`, cache hit `33`, fallback `37`
- Scoring summary: item count `3`, top score `50.03`, top product id `7`, top country `US`, fallback used `true`, AI fallback used `true`
- Truncated performance events: `0`

## Step Metrics

| Step | Status | duration_ms | provider_call_count | qwen_call_count | timeout_count | cache_hit_count | fallback_count |
|---|---|---:|---:|---:|---:|---:|---:|
| `01_company_profiling` | success | 6 | 0 | 0 | 0 | 0 | 0 |
| `02_product_understanding` | success | 13 | 0 | 0 | 0 | 0 | 0 |
| `03_data_collection` | fallback_used | 57 | 12 | 0 | 0 | 12 | 10 |
| `04_competitor_analysis` | fallback_used | 6 | 0 | 0 | 0 | 0 | 0 |
| `05_market_profiling` | fallback_used | 174260 | 6 | 3 | 1 | 6 | 5 |
| `06_content_trend` | fallback_used | 208835 | 3 | 3 | 2 | 3 | 5 |
| `07_opportunity_scoring` | fallback_used | 271780 | 12 | 3 | 3 | 12 | 13 |
| `08_marketing_prep` | fallback_used | 271622 | 0 | 3 | 3 | 0 | 3 |
| `09_report_prep` | fallback_used | 90699 | 0 | 1 | 1 | 0 | 1 |

## Provider And Qwen Summary

| Provider | Endpoint | Calls | Total ms | Max ms | Cache hits | Fallbacks | Timeouts | Statuses |
|---|---|---:|---:|---:|---:|---:|---:|---|
| worldbank | market_profile | 9 | 22 | 6 | 9 | 3 | 0 | cache_hit |
| un_comtrade | trade_data | 9 | 21 | 5 | 9 | 9 | 0 | cache_hit |
| data_source_service | content_trends | 9 | 20 | 4 | 9 | 9 | 0 | cache_hit |
| etsy | search_competitors | 6 | 11 | 2 | 6 | 6 | 0 | cache_hit |

| Model | Operation | Calls | Total ms | Max ms | Fallbacks | Timeouts | Statuses |
|---|---|---:|---:|---:|---:|---:|---|
| qwen3.6-plus | chat | 13 | 1016813 | 90575 | 10 | 10 | success, timeout |

## Focus Steps

### `03_data_collection`

- Step duration: `57 ms`
- Provider duration: `28 ms`
- Qwen duration: `0 ms`
- Counts: provider `12`, Qwen `0`, timeout `0`, cache hit `12`, fallback `10`

| Provider | Endpoint | Countries | Calls | Total ms | Cache hits | Fallbacks | Timeouts | Statuses |
|---|---|---|---:|---:|---:|---:|---:|---|
| worldbank | market_profile | US, JP, GB | 3 | 10 | 3 | 1 | 0 | cache_hit |
| etsy | search_competitors | US, JP, GB | 3 | 6 | 3 | 3 | 0 | cache_hit |
| data_source_service | content_trends | US, JP, GB | 3 | 6 | 3 | 3 | 0 | cache_hit |
| un_comtrade | trade_data | US, JP, GB | 3 | 6 | 3 | 3 | 0 | cache_hit |

### `09_report_prep`

- Step duration: `90699 ms`
- Provider duration: `0 ms`
- Qwen duration: `90575 ms`
- Counts: provider `0`, Qwen `1`, timeout `1`, cache hit `0`, fallback `1`
- Qwen event: `provider=bailian`, `endpoint=chat`, `model=qwen3.6-plus`, `status=timeout`, `duration_ms=90575`, `fallback_used=true`, `json_mode=true`

## Findings

- Production includes the Q31 performance endpoint and schema; this run should not be recorded as undeployed.
- The production baseline was dominated by Qwen wait/timeout time, not provider HTTP/cache time.
- `03_data_collection` was fast on this run because all provider events were cache hits, with CSV fallback flags on most cached records.
- `09_report_prep` spent about 90 seconds in one Qwen chat call, timed out, and used fallback.

## Validation

- `cd backend && py -3.11 -m pytest tests -q`: passed, `291 passed in 20.05s`.
- `cd frontend && npm run lint`: passed, no ESLint warnings or errors.
- `cd frontend && npm run build`: passed, production build compiled successfully.

## Security Notes

- No API key values, cookies, request headers with credentials, `.env` contents, admin password, management password, or raw upstream payloads were recorded.
- Recorded production data is limited to route statuses, safe smoke response fields, workflow ids, step counters, provider labels, durations, cache/fallback/timeout flags, model names, and sanitized errors.
