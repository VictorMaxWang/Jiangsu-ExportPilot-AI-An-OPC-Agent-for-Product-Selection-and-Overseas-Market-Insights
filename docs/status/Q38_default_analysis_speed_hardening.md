# Q38 Default Analysis Speed Hardening

## Summary

The default `/api/analysis/run` flow was hardened without adding a fast/full mode or a frontend choice. The workflow now reuses `03_data_collection.raw_signals` for market profiling, content trend analysis, and opportunity scoring, and uses deterministic structured summaries for the default workflow instead of repeated per-country Qwen calls.

## Old Slow Points

Production `analysis_id=7` on `https://opc.ankangyu.cn` completed as `fallback_used` but took about `661s`.

| Step | Duration |
| --- | ---: |
| `05_market_profiling` | `141998ms` |
| `06_content_trend` | `174494ms` |
| `07_opportunity_scoring` | `271374ms` |
| `08_marketing_prep` | `30022ms` |
| `09_report_prep` | `30103ms` |

The main cause was repeated provider/Qwen work after data collection: market and content steps still performed per-country Qwen summaries, and scoring refetched provider data plus generated row-level Qwen explanations.

## New Strategy

- `03_data_collection` remains the provider collection step and stores deduped product-country `raw_signals`.
- `05_market_profiling` uses preloaded market/trade signals and deterministic summaries in the workflow.
- `06_content_trend` uses preloaded content signals and deterministic analysis in the workflow.
- `07_opportunity_scoring` computes Python scores first from `raw_signals`; default workflow explanations are deterministic and do not call Qwen per row.
- `08_marketing_prep` and `09_report_prep` use a `20s` Qwen limit, with deterministic fallback assets/report content.
- Workflow steps have hard timeout guards. Timeout events are recorded in performance data and the workflow continues as `fallback_used`.
- `DataSourceService` has a service-level provider deadline and can write cached fallback responses when a provider call hangs.

## Compatibility

- No public API schema or frontend request changes.
- Existing dashboard, marketing, and reports data shapes are preserved.
- `OpportunityScore` rows still include reason, risk, next action, sources, evidence, and competitor analysis.
- `workflow_state.marketing_assets`, `workflow_state.reports`, and `next_page_url` remain compatible with existing pages.

## Local Validation

Targeted validation before the full required suite:

| Command | Result |
| --- | --- |
| `cd backend && py -3.11 -m pytest tests/test_analysis_workflow.py -q` | `13 passed in 5.54s` |
| `cd backend && py -3.11 -m pytest tests/test_market_profile_analysis.py tests/test_content_trend_analysis.py tests/test_opportunity_scoring.py tests/test_data_source_service.py -q` | `34 passed in 5.05s` |

Full required validation:

| Command | Result |
| --- | --- |
| `cd backend && py -3.11 -m pytest tests -q` | `310 passed in 18.37s` |
| `cd frontend && npm run lint` | Passed: `No ESLint warnings or errors` |
| `cd frontend && npm run build` | Passed: `Compiled successfully` |
