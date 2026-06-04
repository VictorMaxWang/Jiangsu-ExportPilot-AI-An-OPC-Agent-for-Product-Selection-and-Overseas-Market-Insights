# Q39 Production Default Analysis Speed Validation

- Task id: Q39
- Production target: `https://opc.ankangyu.cn`
- Deployed production commit: `a3786be`
- Validation date: `2026-06-04`
- Analysis id: `8`
- Final status: `fallback_used`

## Summary

Q38 was manually deployed to Tencent Cloud by the user. Production default analysis was validated with the existing production product input and completed in `42552ms`, about `42.6s`.

The default analysis path has dropped from about `939s` to about `42.6s`, and is suitable for competition demo use.

`fallback_used` is the expected stability mechanism for slow or unavailable upstream AI/provider calls. It does not mean the analysis failed.

## Production smoke

| Check | Result |
| --- | --- |
| `GET /health` | OK: service returned healthy backend status |
| `POST /api/ai/smoke/text` | User-provided production result: `success=true` |
| `POST /api/ai/smoke/vision` | User-provided production result: `success=true` |

The Qwen smoke POST checks were not repeated for this record. The final status and performance payload were rechecked through safe read-only production GET endpoints.

## Analysis input

| Field | Value |
| --- | --- |
| `company_id` | `8` |
| `product_id` | `6` |
| `target_countries` | `US`, `JP`, `GB` |
| `competitor_limit` | `20` |

## Production result

| Metric | Value |
| --- | ---: |
| `analysis_id` | `8` |
| Final workflow status | `fallback_used` |
| Total duration | `42552ms` / about `42.6s` |
| `provider_call_count` | `15` |
| `qwen_call_count` | `4` |
| `timeout_count` | `4` |
| `cache_hit_count` | `9` |
| `fallback_count` | `11` |

## Step performance

| Step | Status | Duration | Provider calls | Qwen calls | Timeouts | Cache hits | Fallbacks | Note |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `03_data_collection` | `fallback_used` | `2288ms` / about `2.3s` | `15` | `0` | `0` | `9` | `9` | Provider collection completed quickly with cached fallback sources where needed |
| `05_market_profiling` | `fallback_used` | `6ms` | `0` | `0` | `0` | `0` | `0` | Reused collected signals and deterministic summary |
| `06_content_trend` | `fallback_used` | `6ms` | `0` | `0` | `0` | `0` | `0` | Reused collected signals and deterministic summary |
| `07_opportunity_scoring` | `fallback_used` | `47ms` | `0` | `0` | `0` | `0` | `0` | Deterministic scoring path avoided row-level Qwen calls |
| `08_marketing_prep` | `fallback_used` | `20026ms` / about `20s` | `0` | `3` | `3` | `0` | `1` | Qwen timed out and deterministic marketing fallback was used |
| `09_report_prep` | `fallback_used` | `20083ms` / about `20s` | `0` | `1` | `1` | `0` | `1` | Qwen timed out and deterministic report fallback was used |

## Remaining limits

- `08_marketing_prep` and `09_report_prep` still each spend about `20s` waiting for Qwen timeout fallback. A later optimization can make these artifacts fully on-demand instead of blocking default analysis completion.
- `fallback_used` is an intentional availability and demo-stability state. The workflow completed and produced usable deterministic outputs; this status should not be treated as a failed production validation.

## Local validation

Required validation commands for this Q39 documentation-only change:

| Command | Result |
| --- | --- |
| `cd backend && py -3.11 -m pytest tests -q` | Passed: `310 passed in 23.28s` |
| `cd frontend && npm run lint` | Passed: no ESLint warnings or errors |
| `cd frontend && npm run build` | Passed: production build compiled successfully |

No Key, Cookie, `.env`, management password, `Authorization` value, or database connection string is recorded in this document.
