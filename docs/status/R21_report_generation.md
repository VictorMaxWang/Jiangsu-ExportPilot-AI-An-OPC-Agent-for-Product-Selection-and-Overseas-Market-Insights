# R21 报告生成

- Task id and name: R21 report generation
- Owner thread: R21 报告生成 Agent
- Start time: 2026-05-28T15:10:00+08:00
- End time: 2026-05-28T15:49:02+08:00
- Status: done

## Completed Work

- Added a structured report generator that builds the report from persisted analysis data, dashboard aggregation, opportunity scores, source lineage, and marketing assets.
- Added Bailian `qwen3.6-plus` JSON-mode polishing with deterministic fallback for missing keys, bad JSON, invalid schema, or unsafe report claims.
- Added 13 fixed report sections for 《南通家纺企业海外市场出海选品洞察报告》.
- Added safe backend Markdown-to-HTML rendering without trusting AI-supplied raw HTML.
- Added `/api/reports/generate`, `/api/reports`, `/api/reports/{id}`, and `/api/reports/{id}/download`.
- Rewired the workflow `ReportPrepAgent` to use the new report generator instead of the older 6-section report assembly.
- Replaced the placeholder reports page with report list, generation/regeneration controls, dashboard links, Markdown copy, and disabled PDF buttons.
- Added report detail page with backend HTML preview and Markdown fallback.

## Changed Paths

- `backend/app/api/reports/__init__.py`
- `backend/app/api/router.py`
- `backend/app/schemas/reports.py`
- `backend/app/schemas/__init__.py`
- `backend/app/services/reports/__init__.py`
- `backend/app/services/reports/report_generator.py`
- `backend/app/services/report_service.py`
- `backend/app/services/__init__.py`
- `backend/app/services/ai/prompts.py`
- `backend/app/services/agents/export_insight_workflow.py`
- `backend/tests/test_report_generation.py`
- `backend/tests/test_analysis_workflow.py`
- `frontend/app/_lib/api-client.ts`
- `frontend/app/reports/page.tsx`
- `frontend/app/reports/[id]/page.tsx`
- `frontend/app/reports/_components/ReportsWorkspace.tsx`
- `frontend/app/reports/_components/ReportDetailWorkspace.tsx`
- `frontend/app/globals.css`
- `docs/status/R21_report_generation.md`

## Test Results

```powershell
cd backend
py -3.11 -m compileall app
```

Result: passed.

```powershell
cd backend
py -3.11 -m pytest tests/test_report_generation.py tests/test_analysis_workflow.py -q
```

Result: passed, `6 passed`.

```powershell
cd backend
py -3.11 -m pytest tests -q
```

Result: passed, `157 passed`.

```powershell
cd frontend
node .\node_modules\typescript\bin\tsc --noEmit
npm run lint
npm run build
```

Result: passed. Build generated `/reports` and `/reports/[id]`.

HTTP smoke:

- Started Next production server at `http://127.0.0.1:3004`.
- `GET http://127.0.0.1:3004/reports` returned `200`.

## Security And Data Notes

- No real API keys, tokens, credentials, cookies, request headers, or database URLs were added.
- The frontend does not receive any third-party API key.
- Reports state that competitor samples are directional price/content signals and do not represent real sales.
- Report generation rejects or falls back from unsafe AI wording such as sales forecasts, GMV, bestseller claims, platform rankings, guaranteed conversion, customs certainty, tariff certainty, or certification certainty.
- PDF export remains intentionally disabled in v1; the API returns `501` for `format=pdf`.

## Blockers

- No implementation blockers.

## Follow-up Notes

- The local Next server remains available at `http://127.0.0.1:3004` for review.
- A future PDF implementation should render from the sanitized backend HTML, not raw AI output.
