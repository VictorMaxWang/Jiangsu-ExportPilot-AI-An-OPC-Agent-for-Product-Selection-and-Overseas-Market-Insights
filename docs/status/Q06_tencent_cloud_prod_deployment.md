# Q06 Tencent Cloud production deployment

- Task id: Q06
- Owner thread: Q06 Tencent Cloud production deployment configuration agent
- Start time: 2026-05-29 09:40:00 +08:00
- End time: 2026-05-29 10:03:24 +08:00

## Changed paths

- `.env.example`
- `docker-compose.prod.yml`
- `backend/.dockerignore`
- `backend/Dockerfile`
- `backend/app/core/config.py`
- `backend/tests/test_admin_security.py`
- `frontend/.dockerignore`
- `frontend/Dockerfile`
- `frontend/next.config.mjs`
- `docs/DEPLOYMENT_TENCENT_CLOUD.md`
- `docs/nginx/opc.ankangyu.cn.conf`
- `scripts/deploy_prod.sh`
- `scripts/backup_db.sh`
- `scripts/restore_db.sh`
- `docs/status/Q06_tencent_cloud_prod_deployment.md`

## Work performed

- Added a production-only Docker Compose file for Tencent Cloud CVM deployment.
- Kept local development `docker-compose.yml` unchanged.
- Removed public production exposure for PostgreSQL and Redis by omitting host `ports`.
- Bound backend and frontend production ports to `127.0.0.1` for host Nginx or BT Panel reverse proxy.
- Added production healthchecks for PostgreSQL, Redis, backend, and frontend.
- Hardened backend Docker image startup for reverse proxy use and non-root runtime.
- Converted frontend Dockerfile into dev-default plus production-target multi-stage build.
- Added Docker ignore rules to prevent `.env`, local secrets, caches, logs, and build outputs from entering image contexts.
- Tightened production CORS so only HTTPS origins from environment configuration are allowed.
- Added Nginx, Tencent Cloud deployment, backup, restore, and operational scripts.

## Test results

- `git diff -- docker-compose.yml`: passed, no local compose changes.
- `Select-String -Path docker-compose.prod.yml -Pattern '^\\s+ports:' -Context 1,2`: passed, only backend/frontend publish localhost-bound ports; PostgreSQL and Redis have no `ports`.
- `bash -n scripts/deploy_prod.sh; bash -n scripts/backup_db.sh; bash -n scripts/restore_db.sh`: passed.
- `py -3.11 -m pytest backend/tests/test_admin_security.py`: passed, 8 passed in 3.79s.
- `py -3.11 -m pytest backend/tests`: passed, 183 passed in 12.05s.
- `cd frontend && npm run build`: passed, Next.js 14.2.35 production build completed and generated standalone output.
- `Test-Path frontend/.next/standalone/server.js`: passed, returned `True`.
- `rg --pcre2` scan for real-looking API keys, bearer tokens, and private key blocks in Q06 files: passed, no matches. Placeholder env names and placeholder password strings were reviewed separately.
- `git diff --check`: passed with CRLF normalization warnings only.
- `docker --version; docker compose version`: not run successfully because Docker is not installed or not on PATH in this local environment.

## Blockers

- Local Docker/Compose verification could not be completed on this machine because the `docker` command is unavailable.

## Follow-up notes

- On the Tencent Cloud server, run `docker compose --project-name supinzhihang_prod --env-file .env -f docker-compose.prod.yml config --quiet` before first deployment.
- Keep `.env` only on the server or secret store with file permission `0600`.
- Do not open `5432` or `6379` in Tencent Cloud security groups.
