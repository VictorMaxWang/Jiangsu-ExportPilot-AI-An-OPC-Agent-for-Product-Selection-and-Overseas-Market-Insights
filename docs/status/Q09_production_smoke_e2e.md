# Q09 Production smoke test and end-to-end demo verification

- Task id: Q09
- Owner thread: Q09 production smoke and GitHub issue handler
- Start time: 2026-05-29 14:16:00 +08:00
- End time: 2026-05-29 14:43:11 +08:00

## Environment

- Production URL tested: https://opc.ankangyu.cn
- Health endpoint tested: https://opc.ankangyu.cn/health
- Local workspace: Windows PowerShell, `C:\Users\12804\Desktop\<project-workspace>`
- Repository: `VictorMaxWang/Jiangsu-ExportPilot-AI-An-OPC-Agent-for-Product-Selection-and-Overseas-Market-Insights`
- Git commit SHA tested before this status-only commit: `fd98c25a3564f7d8fa4842543bf5b0931fba3e97`

## Changed paths

- `docs/status/Q09_production_smoke_e2e.md`

## Sanitized HTTP/HTTPS smoke results

| Check | Result |
| --- | --- |
| `HEAD https://opc.ankangyu.cn` | 200, `text/html; charset=utf-8` |
| `GET https://opc.ankangyu.cn/health` | 200, `{"status":"ok","service":"supinzhihang-backend"}` |
| `HEAD https://opc.ankangyu.cn/admin/api-keys` | 200, `text/html; charset=utf-8` |
| `HEAD https://opc.ankangyu.cn/analysis/run` | 200, `text/html; charset=utf-8` |
| `HEAD https://opc.ankangyu.cn/reports` | 200, `text/html; charset=utf-8` |
| `GET https://opc.ankangyu.cn/api/admin/providers/status` without admin credential | 401, `ADMIN_AUTH_REQUIRED` |

Frontend public pages did not return 502 or 404 in the tested HTTP checks.

## Server and admin/provider smoke

- SSH check: `root@opc.ankangyu.cn` with batch-mode public-key auth failed with permission denied.
- Local `ADMIN_PASSWORD` environment check: not set.
- Container smoke on server: not run because SSH/admin access was unavailable.
- Protected provider status/test endpoints: not run because SSH/admin access was unavailable.
- Security note: no `.env`, API key, admin password, cookie, token, Authorization header, database URL, or key backup file was read or printed.

## Browser smoke

Browser automation used `playwright-cli` with Chrome. Screenshots were saved outside the repository at:

```text
C:\Users\12804\AppData\Local\Temp\supinzhihang-q09-smoke
```

Screenshots were not committed.

| Route | Visible page state | Result |
| --- | --- | --- |
| `/` | ExportPilot home page heading rendered | `<main>` present |
| `/companies` | Companies page heading rendered | `<main>` present |
| `/products` | Products page heading rendered | `<main>` present |
| `/admin/api-keys` | Data-source capability status page rendered | `<main>` present |
| `/admin/data-sources` | Data-source capability status page rendered | `<main>` present |
| `/analysis/run` | Run Analysis page rendered | `<main>` present |
| `/marketing` | Marketing content generator page rendered | `<main>` present |
| `/reports` | Reports page rendered | `<main>` present |
| `/dashboard/1` | Analysis dashboard page rendered | `<main>` present |
| `/reports/1` | Report detail page rendered | `<main>` present |

Final browser console check on the active report page reported 0 errors and 0 warnings. An earlier first homepage snapshot observed a missing `/favicon.ico` 404.

## E2E flow outcome

Production API flow completed with fallback states where live AI/provider access failed.

| Step | Result |
| --- | --- |
| Create company | 201, company id `2`, name `E2E Smoke Test Nantong Home Textile` |
| Create products | 201 for product ids `1`, `2`, `3` |
| Generate keywords for product `1` | 502, `BAILIAN_AUTHENTICATION_ERROR` |
| Start analysis | 202, analysis id `1` |
| Poll analysis | Final status `fallback_used`, current step `09_report_prep`, score rows `9` |
| Open dashboard API | 200 for `/api/dashboard/1` |
| Generate marketing content through `/api/marketing/generate` | 502, `BAILIAN_AUTHENTICATION_ERROR` |
| Generate report | 200, report id `1`, markdown length `27300` |
| Open report detail API | 200 for `/api/reports/1`, markdown length `27300` |
| Open dashboard page | Rendered `/dashboard/1` in browser |
| Open report page | Rendered `/reports/1` in browser |

Analysis provider summary:

- Used providers: `bailian`, `csv_seed`, `data_source_service`, `etsy`, `un_comtrade`, `worldbank`
- Fallback-used providers: `bailian`, `data_source_service`, `etsy`, `un_comtrade`
- Report forbidden-claim marker scan found none for: `sales forecast`, `sales prediction`, `guaranteed sales`, `GMV prediction`, `platform-verified revenue`

Cleanup note: the production company, products, analysis, and report were left in place because analysis/report delete endpoints are not available. All created records are identifiable by the `E2E Smoke Test` prefix or by the IDs above.

## Test results

- `cd backend && py -3.11 -m pytest tests -q`: passed, 183 passed in 17.23s.
- `cd frontend && npm run lint`: passed, no ESLint warnings or errors.
- `cd frontend && npm run build`: passed, Next.js 14.2.35 production build completed.

## Bugs found / observations

- Production server SSH access for this agent is not configured, so server-local container smoke and protected admin/provider test endpoints remain blocked.
- Production Bailian direct calls returned `BAILIAN_AUTHENTICATION_ERROR` for keyword and marketing generation. The analysis workflow and report generation continued with fallback behavior.
- A missing `/favicon.ico` 404 was observed during an initial browser snapshot.

## Fixes applied

- No source-code fixes were applied. This task added only the Q09 status document.

## Follow-up tasks

- Configure SSH access or provide a safe admin credential path, then rerun server container and provider tests.
- Verify the production Bailian credential or model access configuration so direct keyword and marketing generation endpoints can pass without fallback.
- Add a favicon or route static favicon requests if the 404 matters for the demo polish.
