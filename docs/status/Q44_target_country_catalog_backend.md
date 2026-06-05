# Q44 Target Country Catalog Backend

- Task id: Q44
- Owner thread: Codex Q44 target country catalog backend thread
- Start time: 2026-06-05 10:45:00 +08:00
- End time: 2026-06-05 11:13:50 +08:00
- Status: done

## Summary

- Added a 19-country target market catalog covering Asia, Europe, North America, Latin America, Oceania, and Africa.
- Added balanced analysis presets: five-continent representatives, mature Western markets, East Asia/Southeast Asia, and Belt and Road potential markets.
- Added DB-first catalog APIs with CSV fallback when catalog tables are empty:
  - `GET /api/markets/countries`
  - `GET /api/markets/presets`
- Added CSV import support for `target_countries.csv` and `analysis_country_presets.csv`.
- Expanded `market_profiles.csv` fallback data so every target country can produce a market profile.
- Enforced shared target-country normalization and max 20 unique countries for analysis, scoring, and market compare requests.
- Added catalog-backed rejection for unknown, disabled, or non-analysis-enabled countries in workflow and scoring paths.
- Updated provider and scoring country mappings for World Bank, GDELT, UN Comtrade, Etsy currency, scoring currency, logistics baseline, and fallback aliases.
- Added `evidence.data_quality` to market profile responses with grain, source mix, fallback availability, freshness, completeness, confidence, checks, and caveats.
- Kept Data Analytics plugin borrowing at the method level only: KPI-style components, market-sizing caveats, and data-quality posture.

## Changed Paths

- `data/seed/target_countries.csv`
- `data/seed/analysis_country_presets.csv`
- `data/seed/market_profiles.csv`
- `backend/app/core/countries.py`
- `backend/app/api/imports.py`
- `backend/app/api/markets/__init__.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/analysis.py`
- `backend/app/schemas/market_content_analysis.py`
- `backend/app/schemas/scoring.py`
- `backend/app/schemas/target_markets.py`
- `backend/app/services/__init__.py`
- `backend/app/services/target_market_catalog.py`
- `backend/app/services/agents/export_insight_workflow.py`
- `backend/app/services/analysis/competitor_analysis.py`
- `backend/app/services/analysis/market_profile_analysis.py`
- `backend/app/services/data_sources/service.py`
- `backend/app/services/importers/csv_importer.py`
- `backend/app/services/providers/etsy.py`
- `backend/app/services/providers/gdelt.py`
- `backend/app/services/providers/un_comtrade.py`
- `backend/app/services/providers/worldbank.py`
- `backend/app/services/scoring/opportunity_scoring.py`
- `backend/tests/test_analysis_api.py`
- `backend/tests/test_data_provider_api.py`
- `backend/tests/test_import_api.py`
- `backend/tests/test_market_profile_analysis.py`
- `backend/tests/test_target_market_catalog.py`
- `docs/status/Q44_target_country_catalog_backend.md`

## Verification

| Command | Result |
| --- | --- |
| `cd backend && py -3.11 -m pytest tests/test_target_market_catalog.py tests/test_market_profile_analysis.py -q` | Passed: 16 passed |
| `cd backend && py -3.11 -m pytest tests/test_import_api.py tests/test_analysis_api.py tests/test_data_provider_api.py -q` | Passed: 33 passed |
| `cd backend && py -3.11 -m pytest tests/test_worldbank_provider.py tests/test_gdelt_provider.py tests/test_un_comtrade_provider.py tests/test_etsy_provider.py -q` | Passed: 44 passed |
| `cd backend && py -3.11 -m pytest tests/test_opportunity_scoring.py tests/test_opportunity_scoring_api.py tests/test_analysis_workflow.py -q` | Passed: 23 passed |
| `cd backend && py -3.11 -m pytest tests/test_data_source_service.py tests/test_dashboard_api.py tests/test_report_generation.py -q` | Passed: 26 passed |
| `cd backend && py -3.11 -m pytest tests -q` | Passed: 329 passed |

## Environment Variables

- No new environment variables were introduced.
- Existing `DATA_COLLECTION_CONCURRENCY` / `SUPIN_DATA_COLLECTION_CONCURRENCY` continues to bound provider fan-out.

## Security Notes

- No secrets, API keys, tokens, cookies, full auth headers, `.env` values, plugin connector IDs, `.app.json` bindings, MCP config, or workspace app bindings were added or copied.
- New catalog APIs return only seed/database market metadata and do not expose provider credentials.
- Data Analytics references were used only as methodology guidance for KPI-style scoring, market-size caveats, and data-quality evidence.

## Blockers

- None.

## Follow-up

- Q45 can connect frontend country selection and report country-name display to the new catalog APIs.
- Future demo-data work can optionally expand competitor, content, and trade sample CSVs for the new countries; Q44 only guarantees market-profile fallback coverage.
