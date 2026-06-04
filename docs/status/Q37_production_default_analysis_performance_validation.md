# Q37 Production Default Analysis Performance Validation

- Task id: Q37
- Production target: `https://opc.ankangyu.cn`
- Local repo path: `D:\Desktop\苏品智航`
- Timestamp: `2026-06-04 08:33:37 +08:00`
- Status: blocked before production deployment

## Summary

Q33-Q36 were validated locally, committed, and pushed to `origin/main`.
Production deployment was not completed because this environment cannot authenticate to the Tencent Cloud CVM over SSH.
Default production analysis was not started, because validating speed before deploying the Q33-Q36 commit would measure the old production build.

## Code pushed

- Commit pushed to `origin/main`: `92451f1`
- Commit message: `Q33-Q36 optimize default analysis performance`

## Local validation before push

| Check | Result |
| --- | --- |
| `git diff --stat` | Reviewed intended Q33-Q36 backend, frontend, test, and status-document changes. |
| `git diff --check` | Passed; only CRLF normalization warnings were printed. |
| `cd backend && py -3.11 -m pytest tests -q` | Passed: `304 passed in 20.78s`. |
| `cd frontend && npm run lint` | Passed: no ESLint warnings or errors. |
| `cd frontend && npm run build` | Passed: production build compiled successfully. |
| `git push origin main` | Passed: `6d95a3c..92451f1 main -> main`. |

## Deployment attempt

The planned production deploy path is `/opt/supinzhihang` on the Tencent Cloud CVM using `bash scripts/deploy_prod.sh`.

SSH reachability was tested with batch-mode authentication only. Both host forms reached an SSH server but rejected the available identity:

| Target | Result |
| --- | --- |
| `root@opc.ankangyu.cn` | Blocked: permission denied for available SSH identity. |
| `root@110.42.218.147` | Blocked: permission denied for available SSH identity. |

Local SSH inspection found no private key under `$HOME\.ssh`, and `ssh-agent` was not running. No `.env`, key, cookie, admin password, database URL, or management password was read or printed.

## Production smoke results

Post-deploy production smoke was not run because deployment did not complete.

| Endpoint | Result |
| --- | --- |
| `GET /health` | Not run as post-deploy smoke. |
| `POST /api/ai/smoke/text` | Not run. |
| `POST /api/ai/smoke/vision` | Not run. |

## Default analysis validation

Default analysis was not started because the Q33-Q36 commit was not deployed to production.

Planned payload after deployment:

```json
{
  "company_id": 8,
  "product_ids": [6],
  "target_countries": ["US", "JP", "GB"],
  "competitor_limit": 20
}
```

Planned product: `product_id=6`, `company_id=8`, an existing confirmed real screenshot/link imported product in production.

| Metric | Result |
| --- | --- |
| Analysis id | Not created. |
| Final status | Not run. |
| Total wall time | Not measured. |
| `performance.duration_ms` | Not measured. |
| `03_data_collection` duration | Not measured. |
| `09_report_prep` duration | Not measured. |
| Provider timeout/fallback | Not measured. |
| Cache hit | Not measured. |

## Page validation

Dashboard, marketing, and reports page validation for the Q37 analysis id was not run because no Q37 analysis id exists yet.

| Page | Result |
| --- | --- |
| `/dashboard/{analysis_id}` | Not run. |
| `/marketing?analysis_id={analysis_id}` | Not run. |
| `/reports?analysis_id={analysis_id}` | Not run. |

## Acceptance status

Q37 acceptance is not met yet.

- Production is reachable over HTTP, but the pushed Q33-Q36 commit is not confirmed deployed.
- The default analysis completion time is not measured.
- The requirement "at least cannot still be running after 10 minutes" is not validated.

## Required next step

Restore SSH access or use the Tencent Cloud/BT Panel terminal, then run the deploy and validation from the production host:

```bash
cd /opt/supinzhihang
git fetch origin main
git checkout main
git pull --ff-only origin main
git rev-parse --short HEAD
bash scripts/deploy_prod.sh
```

Expected deployed commit is `92451f1` or a later commit that includes Q33-Q36.
After deployment, rerun Q37 smoke, default analysis, performance polling, page validation, and update this document with the measured timings.
