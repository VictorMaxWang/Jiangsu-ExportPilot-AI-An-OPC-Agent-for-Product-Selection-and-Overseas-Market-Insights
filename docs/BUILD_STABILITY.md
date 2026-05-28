# Build Stability

This project keeps CI intentionally small: install pinned dependencies, run backend checks, run frontend checks, and record npm audit output without forcing framework upgrades.

## Local clean build

Backend:

```powershell
cd <repo-root>\backend
py -3.11 -m pip install -r requirements.txt
py -3.11 -m pytest tests
py -3.11 -m compileall -q app tests
```

Frontend:

```powershell
cd <repo-root>\frontend

if (Test-Path .next) { Remove-Item -Recurse -Force .next }
if (Test-Path tsconfig.tsbuildinfo) { Remove-Item -Force tsconfig.tsbuildinfo }

npm ci
npm audit --json
npx tsc --noEmit
npm run lint
npm run build
```

If dependency state is suspect, remove `node_modules` before `npm ci`:

```powershell
cd <repo-root>\frontend
if (Test-Path node_modules) { Remove-Item -Recurse -Force node_modules }
npm ci
```

## Common timeout causes

- Running `next dev`, `next start`, or another `next build` in the same `frontend` workspace while a build is writing `.next`.
- Interrupted or stale `.next/cache/webpack` packs, especially on Windows with large cache directories.
- Cold `npm ci` plus cold Next.js production build on a low I/O runner.
- Antivirus or file indexing scanning `.next`, `node_modules`, or webpack cache output.
- A timeout threshold near 60 seconds. Current local builds have completed around 59 to 77 seconds, so CI uses an 8 minute frontend build step timeout.
- Large dashboard bundles. ECharts is imported by client chart components and increases the `/dashboard/[analysis_id]` bundle size, but current source does not perform backend API calls during `next build`.

## CI failure rules

GitHub Actions runs one `ci` job on pull requests and pushes to `main` or `master`.

- Backend fails if dependency installation fails, `python -m pytest tests -q` fails, or `python -m compileall -q app tests` fails.
- Frontend fails if `npm ci`, `npx tsc --noEmit`, `npm run lint`, or `npm run build` fails.
- `npm audit --json` is recorded as `npm-audit-json` artifact and is intentionally non-blocking for Q05 because the current remediation path is a major Next.js upgrade.
- CI uses Python 3.11 and Node 20. Local Windows validation may use `py -3.11`; avoid relying on a bare `python` launcher if it points to another interpreter.

## npm audit record

Current frontend lockfile state on 2026-05-28:

- `next`: 14.2.35
- `eslint-config-next`: 14.2.35
- `react`: 18.3.1
- `react-dom`: 18.3.1
- `echarts`: 6.1.0

`npm audit --json` reports 5 vulnerabilities:

- 4 high
- 1 moderate
- 0 critical

The reported remediation is semver-major:

- `next` -> 16.2.6
- `eslint-config-next` -> 16.2.6

Do not run `npm audit fix --force` as a routine build stabilization step. Treat the audit result as a planned framework upgrade task because it can require Next.js major-version migration work, React compatibility review, and replacing the current `next lint` script if the target Next.js version no longer supports it.

Recommended handling:

- Keep the current `package-lock.json` for reproducible CI.
- Continue recording `npm audit --json` in CI artifacts.
- Open a separate dependency-upgrade task for Next.js and `eslint-config-next`, then run `npm ci`, `npm audit --json`, `npx tsc --noEmit`, `npm run lint`, and `npm run build` on that branch.
