# Q54 Production Upgrade Deployment Validation

- Task id: Q54
- Owner thread: Codex Q54 production deployment validation thread
- Start time: 2026-06-06 12:32:05 +08:00
- End time: 2026-06-06 12:58:45 +08:00
- Production target: `https://opc.ankangyu.cn`
- Production path: `/opt/supinzhihang`

## Summary

Q54 deployment validation is blocked before production upgrade. Local `HEAD`, `main`, and `origin/main` all point to `82a77e1afbe05bf6cae1e0929126e1daa5b33950`, and Q40-Q53 status files are present. The repository has CI only under `.github/workflows/ci.yml`; no production deploy workflow is configured. The latest `main` GitHub Actions run for `82a77e1` completed with failure, and no failed job log was available from `gh run view --log-failed`.

Manual Tencent CVM deployment was attempted with batch-mode SSH only, but the available local identities were rejected by the server before a shell was opened. The production site was therefore not reset to `origin/main`, and `scripts/deploy_prod.sh` was not run.

## Changed Paths

- `docs/status/Q54_upgrade_production_deployment_validation.md`

## Deployment Attempt

Intended server-side deployment command:

```bash
cd /opt/supinzhihang
git fetch origin
git reset --hard origin/main
SKIP_BACKUP_BEFORE_MIGRATION=1 bash scripts/deploy_prod.sh
```

| Check | Result | Notes |
| --- | --- | --- |
| Local commit alignment | Passed | `HEAD`, `main`, and `origin/main` all equal `82a77e1afbe05bf6cae1e0929126e1daa5b33950`. |
| Q40-Q53 status presence | Passed | `docs/status/Q40_*.md` through `docs/status/Q53_*.md` are present. |
| GitHub Actions deploy workflow | Not configured | Only `ci.yml` exists. |
| Latest `main` Actions run | Failed | Run for `82a77e1` is completed/failure; job log retrieval returned no log. |
| SSH to `opc.ankangyu.cn` | Blocked | Public-key authentication was rejected for tested common users. |
| SSH to historical production IP | Blocked | Public-key authentication was rejected for tested common users. |
| Production deploy script | Not run | Server shell was not reached. |
| Backup skip flag | Not executed | `SKIP_BACKUP_BEFORE_MIGRATION=1` is accepted for this Q54 plan, but deployment did not reach the server. |

## HTTP Smoke Results

All checks were run against production from the local Codex workspace after the SSH blocker was confirmed.

| Check | Result | Notes |
| --- | --- | --- |
| `GET /health` | 200 | Backend health route is reachable. |
| `POST /api/ai/smoke/text` | 200 | AI text smoke route is reachable. Response body was not recorded. |
| `POST /api/ai/smoke/vision` | 200 | AI vision smoke route is reachable. Response body was not recorded. |
| `GET /products/import` | 200 | Product import page is reachable. |
| `GET /companies/import` | 404 | Q48 company photo intake page is not deployed. |
| `GET /analysis/run` | 200 | Analysis run page is reachable. |
| `GET /reports` | 200 | Reports page is reachable. |

## Upgrade Route Preflight

| Check | Result | Notes |
| --- | --- | --- |
| `POST /api/product-intake/screenshots` with no file | 404 | Q42 multi-image product upload route is not deployed. |
| `POST /api/company-intake/photo` with no file | 404 | Q47/Q48 company photo route is not deployed. |
| `GET /api/markets/countries` | 404 | Q44/Q45 market catalog route is not deployed. |
| `GET /api/markets/presets` | 404 | Q44/Q45 preset route is not deployed. |
| `GET /api/chat/sessions?limit=1` | 404 | Q49/Q50 global chat route is not deployed. |
| `GET /api/reports/1/versions` | 404 | Q51 report version route is not deployed. |
| `POST /api/reports/proposals/1/confirm` with empty JSON | 404 | Q51 proposal confirmation route is not deployed. |
| `POST /api/analysis/run` with empty JSON | 422 | Existing analysis route is present; empty payload validation failed as expected. |
| `GET /api/reports` | 200 | Existing report list route is reachable. |

## Continuation Recheck

The goal continuation was resumed on 2026-06-06 at 12:55 +08:00. The same blocker remains:

| Check | Result | Notes |
| --- | --- | --- |
| Local commit alignment | Passed | `HEAD`, `main`, and `origin/main` still equal `82a77e1afbe05bf6cae1e0929126e1daa5b33950`. |
| Latest GitHub Actions run | Failed | Latest workflow is still CI for `82a77e1`; no deploy workflow is present. |
| SSH `root@opc.ankangyu.cn` | Blocked | Public-key authentication rejected the available local identity. |
| SSH `ubuntu@opc.ankangyu.cn` | Blocked | Public-key authentication rejected the available local identity. |
| SSH `lighthouse@opc.ankangyu.cn` | Blocked | Public-key authentication rejected the available local identity. |
| SSH `root@110.42.218.147` | Blocked | Public-key authentication rejected the available local identity. |
| `GET /health` | 200 | Production backend is reachable. |
| `GET /companies/import` | 404 | Q48 company photo intake page is still not deployed. |
| `POST /api/product-intake/screenshots` with no file | 404 | Q42 multi-image route is still not deployed. |
| `POST /api/company-intake/photo` with no file | 404 | Q47/Q48 company photo route is still not deployed. |
| `GET /api/markets/countries` | 404 | Q44/Q45 market catalog route is still not deployed. |
| `GET /api/chat/sessions?limit=1` | 404 | Q49/Q50 global chat route is still not deployed. |

## Blocked Audit Recheck

The goal continuation was resumed again on 2026-06-06 at 12:58 +08:00. This is the third consecutive turn with the same deployment blocker: the agent cannot authenticate to the Tencent Cloud server, and production has not been upgraded to Q40-Q53.

| Check | Result | Notes |
| --- | --- | --- |
| Local commit alignment | Passed | `HEAD`, `main`, and `origin/main` still equal `82a77e1afbe05bf6cae1e0929126e1daa5b33950`. |
| Latest GitHub Actions run | Failed | Latest workflow remains CI for `82a77e1`; no deploy workflow is present. |
| SSH `root@opc.ankangyu.cn` | Blocked | DNS resolution had a temporary failure during this retry. |
| SSH `ubuntu@opc.ankangyu.cn` | Blocked | DNS resolution had a temporary failure during this retry. |
| SSH `lighthouse@opc.ankangyu.cn` | Blocked | DNS resolution had a temporary failure during this retry. |
| SSH `root@110.42.218.147` | Blocked | Public-key authentication rejected the available local identity. |
| `GET /health` | 200 | Production backend is reachable over HTTPS. |
| `GET /companies/import` | 404 | Q48 company photo intake page is still not deployed. |
| `POST /api/product-intake/screenshots` with no file | 404 | Q42 multi-image route is still not deployed. |
| `POST /api/company-intake/photo` with no file | 404 | Q47/Q48 company photo route is still not deployed. |
| `GET /api/markets/countries` | 404 | Q44/Q45 market catalog route is still not deployed. |
| `GET /api/chat/sessions?limit=1` | 404 | Q49/Q50 global chat route is still not deployed. |

## Browser Validation

| Scenario | Result | Notes |
| --- | --- | --- |
| Chrome production page inspection | Blocked | Chrome connection was established, but read-only production navigation timed out before useful page assertions were captured. |
| Multi-image product intake | Skipped | Production route `/api/product-intake/screenshots` returns 404. |
| Company photo intake | Skipped | Production page `/companies/import` and route `/api/company-intake/photo` return 404. |
| Five-continent country selection | Skipped | Production route `/api/markets/countries` returns 404. |
| Analysis run with upgraded country catalog | Skipped | Depends on deployed market catalog and created demo records. |
| Report display for Q54 run | Skipped | No Q54 analysis/report was created. |
| Global chat report explanation | Skipped | Production route `/api/chat/sessions` returns 404. |
| Chat-generated report edit proposal | Skipped | Production chat/proposal/version routes return 404. |

## Created Production IDs

No Q54 production company, product, analysis, report, proposal, or version IDs were created. No upload, report edit, or chat write operation was attempted after the deployment blocker and missing-route preflight were confirmed.

## Security Notes

- No API key, token, cookie, `.env` content, admin password, database connection string, or private key content was read, printed, or written.
- SSH checks used batch-mode authentication only.
- AI smoke response bodies were not recorded in this status file.
- No real customer data or private files were uploaded.

## Blockers

- This environment cannot authenticate to the Tencent Cloud CVM over SSH, so the required manual deployment could not be executed.
- Production is still serving a build that lacks Q42, Q44-Q45, Q47-Q51 upgrade routes and the Q48 company import page.
- Full Q54 browser validation cannot be completed until production is upgraded.

## Follow-up Notes

- Restore SSH access for the deploy user or run the deployment commands directly from the Tencent Cloud or BT Panel terminal.
- After deployment, rerun the Q54 HTTP smoke and full browser workflow, then update this status with created safe demo IDs and final pass/fail results.
- If GitHub Actions deployment is preferred, add a separate deploy workflow using repository Secrets and keep logs free of secret values.
