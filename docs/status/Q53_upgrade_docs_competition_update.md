# Q53 upgrade docs competition update

- Task id: Q53
- Task name: 演示数据、文案与比赛材料更新
- Owner thread: Codex Q53 docs and competition update thread
- Start time: 2026-06-06 12:05:00 +08:00
- End time: 2026-06-06 12:19:54 +08:00

## Changed paths

- `README.md`
- `docs/DEPLOYMENT_TENCENT_CLOUD.md`
- `docs/competition/DEMO_SCRIPT_5MIN.md`
- `docs/competition/JUDGES_QA.md`
- `docker-compose.prod.yml`
- `scripts/deploy_prod.sh`
- `docs/status/Q53_upgrade_docs_competition_update.md`

## Summary

- Updated README with core capabilities, production URL, Demo path, competition docs, deployment docs, and security boundaries.
- Updated Tencent Cloud deployment guide for multi-image product upload, company photo upload, global chat, report proposals, report versions, and GitHub Actions deployment.
- Updated production compose and deploy script so company photo uploads use a dedicated persistent volume and upload directory.
- Rewrote the 5-minute demo script around company photo intake, multi-image product intake, five-continent market analysis, global chat report explanation, and chat-driven report versioning.
- Rewrote judges Q&A with reliability, fallback, speed, confirmation, security, and report-edit safeguards.

## Validation

| Command | Result |
| --- | --- |
| `bash -n scripts/deploy_prod.sh` | Passed |
| `git diff --check` | Passed; only line-ending warnings from Git on Windows |
| `py -3.11 -m pytest tests/test_global_chat_api.py tests/test_report_generation.py -q` | Passed: 16 passed |
| `cd frontend && npm run lint` | Passed: no ESLint warnings or errors |
| `cd frontend && npm run build` | Passed: Next.js production build completed |
| `docker compose --env-file .env.example -f docker-compose.prod.yml config --quiet` | Not run: Docker CLI is not installed in this local environment |

## Security notes

- No real API Key, Cookie, Token, admin password, `.env` content, or private credential was written.
- New deployment examples use placeholder Secret names and placeholder values only.
- Report editing remains described as proposal-first and user-confirmed; no direct AI overwrite path is documented.
- Upload docs require privacy cropping and prohibit committing runtime upload volumes.

## Blockers

- Local Docker CLI is unavailable, so production compose syntax could not be validated with Docker. Static review and deploy script syntax checks passed.

## Follow-up notes

- If GitHub Actions auto-deploy is enabled later, create repository Secrets in GitHub settings and avoid printing Secret values in workflow logs.
- After deploying to Tencent Cloud, verify `product_uploads` and `company_uploads` volume permissions with a real upload smoke test.
