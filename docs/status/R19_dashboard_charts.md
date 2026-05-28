# R19 市场看板与图表

- Task id: R19
- Owner thread: R19 市场看板与图表 Agent
- Start time: 2026-05-28T14:05:00+08:00
- End time: 2026-05-28T14:44:10+08:00
- Status: done

## Completed Work

- Added read-only `GET /api/dashboard/{analysis_id}` aggregation from persisted `analysis_runs`, `opportunity_scores`, workflow state, and source metadata.
- Added Dashboard schemas and tests for populated runs, empty-score runs, 404, and scoring-only runs.
- Added ECharts dependency and chart wrappers under `frontend/components/charts/`.
- Added `/dashboard/[analysis_id]` market dashboard page with product score, country score, competitor price range, content theme cloud, recommendation cards, risk cards, data source notes, and EmptyState handling.
- Kept `/dashboard?analysis_id=...` compatible by redirecting to `/dashboard/{analysis_id}` and updated analysis completion links.
- Added the required Demo statement: 当前 Demo 使用 World Bank、GDELT、YouTube、Etsy、UN Comtrade/样本数据与 CSV fallback；平台竞品样本不代表真实销量。

## Changed Paths

- `backend/app/api/dashboard/__init__.py`
- `backend/app/api/router.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/dashboard.py`
- `backend/app/services/__init__.py`
- `backend/app/services/dashboard_service.py`
- `backend/tests/test_dashboard_api.py`
- `frontend/app/_lib/api-client.ts`
- `frontend/app/analysis/run/_components/AnalysisRunWorkspace.tsx`
- `frontend/app/dashboard/page.tsx`
- `frontend/app/dashboard/[analysis_id]/page.tsx`
- `frontend/app/dashboard/_components/DashboardDetailWorkspace.tsx`
- `frontend/components/charts/`
- `frontend/package.json`
- `frontend/package-lock.json`
- `docs/status/R19_dashboard_charts.md`

## Test Results

```powershell
cd backend
py -3.11 -m compileall app
```

Result: passed.

```powershell
cd backend
py -3.11 -m pytest tests/test_dashboard_api.py -q
```

Result: passed, `4 passed`.

```powershell
cd backend
py -3.11 -m pytest tests/test_dashboard_api.py tests/test_opportunity_scoring_api.py tests/test_analysis_api.py -q
```

Result: passed, `11 passed`.

```powershell
cd frontend
node ./node_modules/typescript/bin/tsc --noEmit
npm run lint
npm run build
```

Result: passed. `npm run build` succeeded after stopping old same-project Next dev/start processes that were holding `.next`.

Build and smoke checks:

- `http://127.0.0.1:3003/dashboard/1` returned 200 against a temporary SQLite-backed API on `127.0.0.1:8002`.
- Playwright CLI snapshot confirmed the dashboard rendered the required sections: product score, country recommendation, competitor price range, content theme cloud, recommendation cards, risk cards, and data source notes.
- Playwright CLI DOM check returned `canvasCount: 3`, matching the three ECharts charts.

## Security And Fallback Notes

- No real API keys, tokens, cookies, credentials, request headers, or connection strings were added.
- Dashboard API is read-only and does not call DataSourceService, Bailian, third-party providers, or scoring jobs.
- Frontend displays provider labels, source types, `fallback_used`, and `api_invoked`; it does not expose secret values.
- Competitor price ranges and risk cards explicitly state that platform samples are directional and do not represent real sales.

## Blockers

- None.

## Follow-up Notes

- Local production server is running at `http://127.0.0.1:3003` for review, paired with a temporary seeded FastAPI server at `http://127.0.0.1:8002`.
- `npm install echarts` reported existing dependency audit findings: 1 moderate and 4 high vulnerabilities. No automated audit fix was applied because that would be a broader dependency change.
