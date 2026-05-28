# R18 智能体运行过程页面

- Task id: R18
- Owner thread: R18 智能体运行过程页面 Agent
- Start time: 2026-05-28T13:36:00+08:00
- End time: 2026-05-28T14:12:09+08:00
- Status: done

## 完成内容

- 将 `/analysis/run` 从静态占位页改为真实可交互页面。
- 新增企业选择、产品选择、目标国家、竞品采集上限、完成后跳转目标等分析启动参数。
- 接入 R17 后端工作流：
  - `POST /api/analysis/run`
  - `GET /api/analysis/{analysis_id}/status`
- 每 1.5 秒串行轮询一次状态，避免请求重叠；整体状态进入 `success`、`fallback_used`、`failed` 或存在 `finished_at` 后停止轮询。
- 展示 9 个智能体节点：
  - 企业画像智能体
  - 产品理解智能体
  - 数据采集智能体
  - 竞品分析智能体
  - 市场画像智能体
  - 内容趋势智能体
  - 机会评分智能体
  - 营销准备智能体
  - 报告准备智能体
- 支持 `waiting`、`running`、`success`、`failed`、`fallback_used` 状态样式。
- 对 `fallback_used` 明确展示：“该步骤使用本地样本数据保障演示稳定。”
- 分析完成后按页面选择跳转报告页或看板页；报告页优先使用后端返回的 `next_page_url`。
- 新增 `frontend/lib/api.ts` re-export，兼容任务要求的 API 入口，同时保留现有 `frontend/app/_lib/api-client.ts` 调用模式。
- 未写入、读取或展示任何第三方 API Key、token、cookie 或密钥值。

## Changed Paths

- `frontend/app/_lib/api-client.ts`
- `frontend/lib/api.ts`
- `frontend/components/agent-flow/AgentFlowTimeline.tsx`
- `frontend/components/agent-flow/index.ts`
- `frontend/app/analysis/run/page.tsx`
- `frontend/app/analysis/run/_components/AnalysisRunWorkspace.tsx`
- `docs/status/R18_agent_run_page.md`

## Test Results

```powershell
cd frontend
node ./node_modules/typescript/bin/tsc --noEmit
```

Result: passed.

```powershell
cd frontend
node ./node_modules/eslint/bin/eslint.js app components lib --ext .ts,.tsx
```

Result: passed, no warnings.

```powershell
cd frontend
npm run build
```

Result: timed out after 244 seconds. No TypeScript or ESLint error was returned before timeout.

```powershell
cd frontend
node ./node_modules/next/dist/bin/next build --no-lint
```

Result: timed out after 364 seconds. This matches the previously recorded local Next build startup/timeout limitation in R12.

Browser verification:

- Codex Browser plugin was attempted first, but the in-app browser runtime reported that the browser client was not trusted in this session.
- A separate Next dev server was started on `http://127.0.0.1:3334`, but it remained at `Starting...` for more than 60 seconds and did not serve `/analysis/run`.
- Existing `http://127.0.0.1:3000/analysis/run` returned HTTP 500 from an older local dev server process, so it was not used as acceptance evidence.
- The temporary `3334` dev server process was stopped after verification attempts.

## Subagent Notes

- `workflow-ui-agent`: confirmed R17 API contract, status enum, 9 step ids, terminal status rules, and `next_page_url` behavior.
- `polling-agent`: recommended typed client additions, 1.5 second `setTimeout` polling, abort handling, stale response guard, and terminal stop rules.
- `ux-agent`: confirmed R11 visual language and demo emphasis: existing card shell, `river`/`jade`/`wheat` status tones, honest fallback labeling.
- `integration-agent`: confirmed R12 enterprise/product list APIs, field names, company-product association, and `/api/analysis/run` input format.

## Blockers

- None for implementation.
- Local browser/build verification is limited by the current Next runtime behavior on this machine; static TypeScript and ESLint checks passed.

## Follow-up Notes

- Re-run browser verification in an environment where Next dev or production start reaches ready state. The page is designed to show a backend-unavailable error if FastAPI is not running, and to run the full demo flow when `/api/companies`, `/api/products`, and `/api/analysis/run` are available.
