# S02 GitHub Actions Auto Deploy

- Task id: S02
- Owner thread: Codex GitHub Actions auto deploy implementation thread
- Start time: 2026-06-06 19:40:05 +08:00
- End time: 2026-06-06 20:10:24 +08:00
- Production target: `https://opc.ankangyu.cn`
- Production path: `/opt/supinzhihang`

## Summary

Added a dedicated GitHub Actions production deployment workflow. The workflow runs backend tests and frontend checks on GitHub-hosted runners before deploying `origin/main` to the Tencent Cloud CVM over SSH.

## Automatic Deployment Mechanism

- Workflow file: `.github/workflows/deploy.yml`
- Triggers: `push` to `main` and manual `workflow_dispatch`
- Concurrency: `production-deploy`, with no parallel production deploy runs
- Permissions: `contents: read` only
- Runners: GitHub-hosted `ubuntu-latest`; no self-hosted runner is used
- Backend gate: Python 3.11, `backend/requirements.txt`, `python -m pytest tests -q`
- Frontend gate: Node 20, `npm ci`, `npm run lint`, `npm run build`
- Deploy gate: the deploy job runs only after both check jobs pass

The deploy job writes `TENCENT_SSH_KEY` into a temporary runner file, connects to the CVM with SSH, and executes:

```bash
cd /opt/supinzhihang
git fetch origin
git reset --hard origin/main
sed -i 's/\r$//' scripts/*.sh
chmod +x scripts/*.sh
SKIP_BACKUP_BEFORE_MIGRATION=1 bash scripts/deploy_prod.sh
curl http://127.0.0.1:8000/health
curl -I https://opc.ankangyu.cn
curl -sS -X POST https://opc.ankangyu.cn/api/ai/smoke/text -H 'Content-Type: application/json' -d '{}'
```

The workflow does not modify the server `.env`.

## Required Repository Secrets

Configure these in GitHub repository settings under Actions secrets:

```text
TENCENT_HOST
TENCENT_PORT
TENCENT_USER
TENCENT_SSH_KEY
```

Do not store `.env`, API keys, cookies, admin passwords, Authorization values, or database connection strings in workflow files, artifacts, status files, screenshots, or public logs.

## Manual Trigger

1. Open the GitHub repository.
2. Go to Actions.
3. Select `Deploy Production`.
4. Choose `Run workflow`.
5. Select branch `main`.
6. Start the run and inspect only non-sensitive logs if it fails.

## Troubleshooting

- If `backend tests` fails, reproduce locally with `cd backend && py -3.11 -m pytest tests -q`.
- If `frontend checks` fails, reproduce locally with `cd frontend && npm run lint` and `cd frontend && npm run build`.
- If SSH fails, verify the four repository Secrets, the deploy user's authorized key, the CVM security group, and the SSH port.
- If `git reset --hard origin/main` fails, verify the server repository remote and deploy user permissions under `/opt/supinzhihang`.
- If `scripts/deploy_prod.sh` fails, inspect Docker Compose status and server disk/memory, but do not print `.env`.
- If smoke checks fail, verify `http://127.0.0.1:8000/health`, Nginx for `https://opc.ankangyu.cn`, and the production AI configuration without exposing secret values.

## Changed Paths

- `.github/workflows/deploy.yml`
- `docs/DEPLOYMENT_TENCENT_CLOUD.md`
- `docs/status/S02_github_actions_auto_deploy.md`

## Test Results

| Check | Result |
| --- | --- |
| `cd backend && py -3.11 -m pytest tests -q` | Passed: 357 tests passed. |
| `cd frontend && npm run lint` | Passed: no ESLint warnings or errors. |
| `cd frontend && npm run build` | Passed: Next.js production build completed. |
| `git diff --check -- .github/workflows/deploy.yml docs/DEPLOYMENT_TENCENT_CLOUD.md docs/status/S02_github_actions_auto_deploy.md` | Passed: no whitespace errors; Git warned that `docs/DEPLOYMENT_TENCENT_CLOUD.md` may be normalized to CRLF on next touch in this Windows checkout. |
| Backend clean-env retry with third-party key/provider env vars removed | Passed: 357 tests passed. |

## Push Validation

- Initial commit `b1de79f` was pushed to `main` and triggered `.github/workflows/deploy.yml`, but GitHub reported a workflow-file issue before any jobs were created.
- The deploy workflow was updated to avoid job-level use of `runner.temp`; runner-specific paths now live in step-level environment variables.
- The existing `.github/workflows/ci.yml` push run for the same commit also reported a workflow-file issue before jobs were created. This appears to be an existing CI workflow problem and was not changed in S02.
- Follow-up commit `da2c15b` triggered `Deploy Production` run `27061799204`; the workflow created jobs, frontend checks passed, backend tests failed because job-level empty key/provider env vars overrode test fake settings, and deploy was skipped by `needs`.
- The deploy workflow was updated again to avoid injecting third-party key or provider toggle env vars into backend tests.

## Blockers

- None for repository-side workflow implementation.
- Actual production deployment depends on valid GitHub Repository Secrets and SSH access from GitHub-hosted runners to the Tencent Cloud CVM.

## Follow-up Notes

- After the first successful `main` push deployment, confirm the workflow run completed and production smoke checks passed.
- Keep deployment logs limited to non-sensitive command results and status summaries.
