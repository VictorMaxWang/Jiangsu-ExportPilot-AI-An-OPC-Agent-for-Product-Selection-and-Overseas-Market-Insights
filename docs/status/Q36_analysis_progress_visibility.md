# Q36 Analysis Progress Visibility

## Summary

优化 `/analysis/run` 前端进度体验，不新增快速模式。页面现在同时轮询分析状态与 `/api/analysis/{id}/performance`，让用户能看到当前卡在哪一步、各智能体耗时与调用计数、是否出现 cache/fallback/timeout，以及评分生成后是否可以先查看看板。

## Implemented Behavior

- `/analysis/run` 运行中持续轮询 status 与 performance，不再使用短轮询保护上限提前停止。
- 顶部进度条展示 `已完成 x/9`、当前步骤、总运行时间、最近一次状态更新时间和整体状态。
- 每个智能体卡片展示状态、已运行时间、`duration_ms`、`provider_call_count`、`qwen_call_count`、`cache_hit_count`、`fallback_count`、`timeout_count`。
- 单步运行或最终耗时超过 60 秒时展示提示：`该步骤耗时较长，系统正在尝试缓存或样本数据兜底。`
- `scoring_summary.item_count > 0` 后立即允许点击 `查看当前看板`，即使报告步骤仍在生成。
- 报告未完成但看板可用时展示 `报告可稍后生成，不影响看板查看`。
- 新增 `性能慢点` 区块，只展示 performance 的安全聚合字段：step title/status/duration 与 provider/qwen/cache/fallback/timeout 计数。
- 新增进度与性能区块文案接入现有中/EN 切换，默认中文保持不变。

## Changed Paths

- `frontend/app/analysis/run/_components/AnalysisRunWorkspace.tsx`
- `frontend/components/agent-flow/AgentFlowTimeline.tsx`
- `docs/status/Q36_analysis_progress_visibility.md`

## Security

前端仅展示 whitelisted 聚合字段，不渲染 raw performance events、Key、Cookie、管理密码、原始请求头或未过滤请求 payload。

## Verification

- `cd frontend && npm run lint`
  - Passed: `No ESLint warnings or errors`
- `cd frontend && npm run build`
  - Passed: `Compiled successfully`
- Local browser smoke: `http://127.0.0.1:3101/analysis/run`
  - Passed in system Chrome: HTTP `200`, rendered `运行分析`, `已完成`, `性能慢点`, and `EN` toggle.

## Timing

- Owner thread: Codex
- Completed at: `2026-06-04 08:06:28 +08:00`

## Follow-up Notes

手动验证需要连接可用后端并启动一次分析，重点检查评分产出后看板入口是否提前出现、报告未完成提示是否显示，以及超过 60 秒步骤的慢步骤提示。
