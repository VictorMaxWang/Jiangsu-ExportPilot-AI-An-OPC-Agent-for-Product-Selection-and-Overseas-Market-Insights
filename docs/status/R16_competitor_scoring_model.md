# R16 Competitor Scoring Model

- Task id: R16
- Owner thread: R16 competitor analysis and opportunity scoring Agent
- Start time: 2026-05-28T11:05:00+08:00
- End time: 2026-05-28T11:21:16+08:00
- Status: done

## Completed Work

- Added deterministic competitor analysis for price bands, common terms, competition level, pricing suggestion, and summary.
- Added opportunity scoring service for product x country scoring with fixed Python weights.
- Added strict Qwen explanation flow where AI can only return `reason`, `risk`, and `next_action`; invalid score-bearing AI output falls back to deterministic explanation.
- Added `/api/scoring/run` and `/api/scoring/results/{analysis_id}`.
- Extended `opportunity_scores` persistence with `next_action`, fallback flags, sources, evidence, and competitor analysis JSON.
- Kept all data access routed through `DataSourceService`; no eBay provider, API call, cache, or log path was added.

## Changed Paths

- `backend/alembic/versions/20260528_0004_extend_opportunity_scores_for_r16.py`
- `backend/app/api/router.py`
- `backend/app/api/scoring/__init__.py`
- `backend/app/models/analysis.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/analysis.py`
- `backend/app/schemas/scoring.py`
- `backend/app/services/__init__.py`
- `backend/app/services/ai/prompts.py`
- `backend/app/services/analysis/__init__.py`
- `backend/app/services/analysis/competitor_analysis.py`
- `backend/app/services/scoring/__init__.py`
- `backend/app/services/scoring/opportunity_scoring.py`
- `backend/tests/test_opportunity_scoring.py`
- `backend/tests/test_opportunity_scoring_api.py`
- `docs/status/R16_competitor_scoring_model.md`

## Test Results

```powershell
py -3.11 -m pytest backend/tests/test_opportunity_scoring.py backend/tests/test_opportunity_scoring_api.py -q
```

Result: passed, `8 passed`.

```powershell
py -3.11 -m pytest backend/tests -q
```

Result: passed, `137 passed`.

## Security And Fallback Notes

- No real API keys, tokens, cookies, credentials, request headers, or secret values were added.
- Qwen receives computed score dimensions and evidence only for explanation; Python remains the only source of scoring values.
- Qwen output containing score fields is rejected by strict schema validation and replaced with deterministic fallback text.
- Etsy competitor data is accessed through `DataSourceService`; provider failure or missing credentials falls back to `data/seed/competitor_samples.csv`.
- eBay remains unsupported for MVP runtime: no eBay client is imported, called, cached, or logged by R16.

## Blockers

- None.

## Follow-up Notes

- Frontend dashboard and report flows can consume the persisted `opportunity_scores` rows and source/evidence JSON from the scoring results API.
