# Q05 CI dependency audit

- Task id: Q05
- Owner thread: Q05 CI dependency audit and build stability agent
- Start time: 2026-05-28 20:33:07 +08:00
- End time: 2026-05-28 20:38:12 +08:00

## Changed paths

- `.github/workflows/ci.yml`
- `docs/BUILD_STABILITY.md`
- `docs/status/Q05_ci_dependency_audit.md`

## Work performed

- Added GitHub Actions CI for backend and frontend checks.
- Fixed CI runtime versions at Python 3.11 and Node 20.
- Added a non-blocking npm audit artifact step.
- Documented clean build steps, timeout causes, CI failure criteria, and current npm audit findings.

## Test results

- `cd backend && py -3.11 -m pytest tests`: passed, 177 passed in 12.33s.
- `cd backend && py -3.11 -m compileall -q app tests`: passed.
- `cd frontend && npm audit --json`: exited 1 as expected because audit findings remain recorded; 5 vulnerabilities total.
- `cd frontend && npx tsc --noEmit`: passed.
- `cd frontend && npm run lint`: passed, no ESLint warnings or errors.
- `cd frontend && npm run build`: passed, Next.js 14.2.35 production build completed in 61.7s locally.

## npm audit result

Current `frontend` audit result from `npm audit --json`:

- Total vulnerabilities: 5
- High: 4
- Moderate: 1
- Critical: 0
- Main packages involved: `next`, `eslint-config-next`, transitive `glob`, transitive `postcss`
- npm reported fix target: `next@16.2.6` and `eslint-config-next@16.2.6`
- Decision: do not run `npm audit fix --force`; treat as a separate framework upgrade task.

## Blockers

- None for Q05 implementation.
- Dependency audit remains a known risk until a controlled Next.js major upgrade is planned and tested.

## Follow-up notes

- CI intentionally does not use real third-party API keys.
- CI records npm audit output as an artifact instead of failing the build on known Next.js major-upgrade findings.
- Python dependency security audit is out of scope for Q05 because no Python audit tool is configured in this repository.
