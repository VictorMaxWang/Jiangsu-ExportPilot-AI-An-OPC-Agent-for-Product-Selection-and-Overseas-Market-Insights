# Q26 Real Intake Production Closure - Blocked

- Task id: Q26
- Owner thread: Codex production closure agent
- Start time: 2026-05-30
- Current status time: 2026-05-31T10:35:12+08:00
- Status: blocked, incomplete

## Scope

Validate the production site at `https://opc.ankangyu.cn` for two product intake paths:

- Marketplace URL intake for Taobao, Pinduoduo, and JD links.
- Marketplace screenshot upload intake using real Qwen vision or controlled fallback/manual-required draft creation.

The full goal also requires at least one confirmed product and a production flow through analysis, dashboard, marketing, and reports.

## Changed Paths

- `backend/app/services/product_intake/screenshot_analyzer.py`
- `backend/tests/test_product_intake_screenshot_api.py`
- `scripts/deploy_prod.sh`

The functional screenshot-upload changes were committed and pushed earlier as
`60e30ed4556fcd1db746d318fad2baf0aaca4fa3`.

## Deployment State

- Functional fix commit included in latest main: `60e30ed4556fcd1db746d318fad2baf0aaca4fa3`
- Deploy target: latest `main` that includes the functional fix commit above.
- Production screenshot upload retest at `2026-05-31T10:35:12+08:00`: HTTP 500
- Conclusion: the pushed screenshot upload fix has not been deployed to production, or production is still not running it.

## Production URL Intake Results

Using company `E2E 智能导入测试企业`:

| Source | URL | Result |
| --- | --- | --- |
| Taobao | `https://e.tb.cn/h.Rg7IXlmjiRJ5ifv?tk=S71r5yDJd3y` | Controlled `needs_screenshot`; no HTTP 500; platform recognized as Taobao; no `URL_HOST_NOT_ALLOWED` |
| Pinduoduo | `https://mobile.yangkeduo.com/goods2.html?ps=zheeHWNSNR` | Controlled `needs_screenshot`; no HTTP 500; platform recognized as Pinduoduo |
| JD | `https://3.cn/-2Q1WvH7?jkl=@X59VX7JUQ1@` | Parsed URL path; Qwen text path returned manual-required product draft; no HTTP 500; no `URL_HOST_NOT_ALLOWED` |

## Screenshot Import Result

- A sanitized local reference screenshot was used for production upload testing.
- A minimal valid 1x1 PNG was also uploaded to rule out a malformed screenshot fixture.
- Production endpoint still returns HTTP 500 for both files.
- This is the remaining functional blocker.

## Product And Downstream Flow

- Confirmed product id: `5`
- Confirmed draft id: `11`
- Analysis id: `3`
- Report id after regeneration: `5`
- Analysis completed for `US`, `JP`, and `GB` with three opportunity score rows.
- Dashboard, marketing, and report pages returned HTTP 200.
- Report `5` was audited for prohibited sales/GMV claims and did not contain the checked forbidden terms.

## Test Results

- `cd backend && py -3.11 -m pytest tests -q`: passed, `288 passed`
- `cd frontend && npm run lint`: passed, no ESLint warnings or errors
- `cd frontend && npm run build`: passed

## Blockers

- Chrome extension control repeatedly failed before it could claim the OrcaTerm tab.
- Computer Use / `node_repl` automation runtime currently fails even on a minimal probe, so it cannot control Chrome or OrcaTerm.
- No alternate deploy path is available from this environment:
  - no SSH key/config for the server
  - no Tencent CLI
  - no GitHub deploy workflow
  - no GitHub Actions deploy secrets or variables

## Required Follow-up

1. Restore the Codex Chrome/Computer Use runtime, or manually run the deployment in the existing Tencent Cloud OrcaTerm session.
2. On the server, deploy latest `main` that includes `60e30ed4556fcd1db746d318fad2baf0aaca4fa3`.
3. Retest screenshot upload and verify it returns a controlled draft result instead of HTTP 500.
4. If screenshot upload passes, create the requested completion file `docs/status/Q26_real_intake_goal_completion.md`, then commit and push it.
