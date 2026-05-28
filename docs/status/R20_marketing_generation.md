# R20 Marketing Generation

- Task id and name: R20 marketing generation
- Owner thread: R20 marketing copy generation Agent
- Start time: 2026-05-28T14:08:00+08:00
- End time: 2026-05-28T14:51:26+08:00
- Status: done

## Completed Work

- Added business API `POST /api/marketing/generate`.
- Added `MarketingGenerator` service using backend Bailian `qwen3.6-plus` JSON mode.
- Added strict marketing prompt rules against sales forecasts, guaranteed conversion, invented certifications, reviews, rankings, customs certainty, and profit claims.
- Added exact seven-field response contract for report-ready marketing drafts.
- Added optional persistence into `AnalysisRun.workflow_state["marketing_assets"]`.
- Replaced the static `/marketing` page with an interactive workspace.
- Added analysis-id hydration, manual input mode, generation flow, output sections, and clipboard copy controls.
- Kept all key handling backend-only; no frontend key exposure was added.

## Changed Paths

- `backend/app/api/marketing/__init__.py`
- `backend/app/api/router.py`
- `backend/app/schemas/marketing.py`
- `backend/app/schemas/__init__.py`
- `backend/app/services/marketing/__init__.py`
- `backend/app/services/marketing/generator.py`
- `backend/app/services/__init__.py`
- `backend/app/services/ai/prompts.py`
- `backend/app/services/agents/export_insight_workflow.py`
- `backend/tests/test_marketing_generation.py`
- `frontend/app/_lib/api-client.ts`
- `frontend/app/marketing/page.tsx`
- `frontend/app/marketing/_components/MarketingWorkspace.tsx`
- `docs/status/R20_marketing_generation.md`

## Test Results

```powershell
cd backend
py -3.11 -m pytest tests/test_marketing_generation.py -q
```

Result: passed, `5 passed`.

```powershell
cd backend
py -3.11 -m pytest tests/test_marketing_generation.py tests/test_ai_integration.py -q
```

Result: passed, `18 passed`.

```powershell
cd backend
py -3.11 -m pytest tests -q
```

Result: passed, `152 passed`.

```powershell
cd frontend
npm run lint
```

Result: passed, no ESLint warnings or errors.

```powershell
cd frontend
npm run build
```

Result: passed after cleaning a stale generated `.next` directory left by an older dev server. Final build generated `/marketing`.

HTTP smoke checks:

- `GET http://127.0.0.1:3000/marketing`: `200`, page contains `Marketing content generator`.
- `POST http://127.0.0.1:8001/api/marketing/generate` without Bailian key: sanitized `BAILIAN_NOT_CONFIGURED` response that mentions `BAILIAN_API_KEY` or `DASHSCOPE_API_KEY`.

## Browser Validation

- Attempted Browser plugin validation for `/marketing`.
- Browser plugin connection failed before navigation due a local Browser runtime trust/bridge issue.
- Fallback validation used build, lint, backend tests, direct HTTP route smoke, and API missing-key smoke.

## Security Notes

- No real API keys, tokens, cookies, credentials, request headers, or upstream raw sensitive payloads were written.
- The frontend calls only the backend marketing API.
- Missing Bailian configuration returns a sanitized message and does not expose headers or key material.

## Blockers

- In-app Browser validation was blocked by the local Browser plugin runtime connection failure.

## Follow-up Notes

- The task board has older R20 wording, but this status file follows the current user instruction naming R20 as marketing generation.
- With a real backend `BAILIAN_API_KEY` or `DASHSCOPE_API_KEY`, `/api/marketing/generate` should produce reusable English marketing content through `qwen3.6-plus`.
