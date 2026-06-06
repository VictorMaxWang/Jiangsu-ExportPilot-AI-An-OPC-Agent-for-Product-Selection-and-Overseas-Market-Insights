# Q52 Upgrade E2E Validation

- Task id: Q52
- Owner thread: Codex desktop thread `019e9b07-86d9-7933-a9b3-05ea43184042`
- Start time: 2026-06-06 11:54:32 +08:00
- End time: 2026-06-06 12:01:52 +08:00

## Summary

Q52 production validation was started against `https://opc.ankangyu.cn` with the planned rule that missing production routes must be treated as blockers instead of working around them. Production health and several legacy APIs are reachable, but the deployed backend is missing multiple Q52 upgrade routes. Because the chain is blocked before company photo intake, multi-image product upload, market catalog selection, global chat, and report versioning, no Q52 production records were created.

The required local regression checks passed.

## Changed Paths

- `docs/status/Q52_upgrade_e2e_validation.md`

## Production Preflight

Live route checks, all run on 2026-06-06 from the local Codex desktop workspace:

| Check | Result | Notes |
| --- | --- | --- |
| `GET /health` | 200 | Backend health returned `supinzhihang-backend`. |
| `GET /api/companies` | 200 | Existing production companies listed. |
| `GET /api/products` | 200 | Existing production products listed. |
| `GET /api/product-intake/drafts?limit=1` | 200 | Product draft listing exists. |
| `POST /api/product-intake/screenshot` validation-only request | 422 | Single-image route exists; validation failed because no file was sent. |
| `POST /api/product-intake/screenshots` validation-only request | 404 | Multi-image Q52 product upload route is missing in production. |
| `GET /api/company-intake/drafts` | 404 | Company intake draft route is missing in production. |
| `POST /api/company-intake/photo` validation-only request | 404 | Company photo upload route is missing in production. |
| `GET /api/markets/countries` | 404 | Target-market catalog route is missing in production. |
| `GET /api/markets/presets` | 404 | Target-country preset route is missing in production. |
| `POST /api/analysis/run` validation-only request | 422 | Analysis route exists; validation failed because empty JSON was sent. |
| `GET /api/analysis/1/status` | 200 | Existing analysis status route works. |
| `GET /api/analysis/1/performance` | 200 | Existing analysis performance route works. |
| `GET /api/dashboard/1` | 200 | Existing dashboard route works. |
| `GET /api/reports` | 200 | Existing reports list route works. |
| `POST /api/reports/generate` validation-only request | 422 | Report generation route exists; validation failed because empty JSON was sent. |
| `GET /api/reports/1/versions` | 404 | Q51 report versions route is missing in production. |
| `GET /api/chat/sessions?limit=1` | 404 | Q49/Q50 global chat route is missing in production. |

## Test Assets

Synthetic, non-private PNG assets were generated outside the repository under:

```text
C:\Users\12804\AppData\Local\Temp\q52-e2e-assets
```

Created files:

- `q52-company-business-card.png`
- `q52-company-catalog.png`
- `q52-product-main.png`
- `q52-product-detail.png`
- `q52-product-package.png`

The images contain only Q52 labels and safe demo text. They were not uploaded because production preflight failed.

## E2E Step Results

| Step | Result | Fallback / blocker |
| --- | --- | --- |
| Production health | Success | `/health` returned 200. |
| Company photo upload to `company_draft` | Skipped | Blocked by missing `/api/company-intake/photo` and `/api/company-intake/drafts` routes. |
| Company draft confirm to company record | Skipped | Dependent on company photo intake. |
| Product multi-image upload to `product_draft` | Skipped | Blocked by missing `/api/product-intake/screenshots`; single-image legacy route exists only. |
| Product draft confirm to product record | Skipped | Dependent on Q52 multi-image product draft. |
| Five-continent country selection | Skipped | Blocked by missing `/api/markets/countries`; target list `JP, DE, US, BR, AU, ZA` was not submitted. |
| Analysis run and polling | Skipped | Analysis route exists, but Q52 target catalog and new confirmed records were unavailable. |
| Dashboard validation | Skipped for Q52 run | Existing dashboard route works, but no Q52 analysis was created. |
| Global chat report explanation | Skipped | Blocked by missing `/api/chat/sessions`. |
| Chat-generated report edit proposal | Skipped | Blocked by missing global chat route. |
| Apply proposal to create `report_versions` version | Skipped | Blocked by missing `/api/reports/{id}/versions` and proposal workflow routes. |
| Report prohibited-claim validation | Skipped for Q52 report | No Q52 report/proposal was created. Existing report generation and quality checks are covered by local tests. |

## Browser / UI Notes

- Browser plugin was attempted for read-only production UI checks.
- The in-app Browser timed out while navigating production pages, so no accepted Browser screenshots were captured.
- Because production API preflight already showed hard blockers, no UI uploads or form submissions were attempted.

## Verification Results

| Command | Result |
| --- | --- |
| `cd backend && py -3.11 -m pytest tests -q` | Passed: `357 passed in 28.33s`. |
| `cd frontend && npm run lint` | Passed: no ESLint warnings or errors. |
| `cd frontend && npm run build` | Passed: Next.js production build completed successfully. |

## Security And Claims Review

- No production Q52 records, reports, proposals, or report versions were created.
- No real API keys, tokens, cookies, authorization headers, or private data were written to this status file.
- The route checks did not include request headers or secret-bearing payloads.
- Synthetic test assets intentionally avoid real customer data and avoid claims about real sales, GMV, guaranteed sales, guaranteed conversion, sales forecasts, or bestseller ranking.

## Blockers

- Production is not deployed with the latest Q49-Q52 backend routes:
  - Missing company photo intake API.
  - Missing multi-image product upload API.
  - Missing target-market catalog API.
  - Missing global chat API.
  - Missing report versions API.
- Browser UI inspection was limited by in-app Browser navigation timeout.

## Follow-up Notes

- Deploy the current backend and frontend that include Q49-Q52 routes, then rerun this Q52 validation with the temp Q52 assets or regenerated equivalents.
- After deployment, rerun the full production chain and record created company, product, analysis, report, proposal, and version IDs.
- Keep `agent.md` and `docs/TASK_BOARD.md` unchanged unless the control thread coordinates a task-board update.
