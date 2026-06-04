# Q35 Report/Marketing Timeout Fallback

## Summary

默认分析流程现在对营销与报告阶段的 Qwen 调用设置显式超时，使用现有 `BAILIAN_TIMEOUT_SECONDS` 配置，默认值为 `30.0s`。没有新增快速模式；默认流程在评分完成后即使 Qwen 报告或营销生成变慢，也会落到可查看的 deterministic fallback 结果，并让 analysis 进入 `success` 或 `fallback_used`，不会长期保持 `running`。

## Implemented Behavior

- 新增共享 helper：`app.services.ai.qwen_timeout.wait_for_qwen`。
- `PerformanceBailianClient` 在 `asyncio.CancelledError` 下记录安全的 Qwen timeout event，后续 fallback 会把该 event 标记为 `fallback_used`，step 统计可看到 timeout/fallback count。
- `08_marketing_prep` 先构建 top score asset context，再对当前 top 3 营销 Qwen 调用并发执行，每个调用使用 `BAILIAN_TIMEOUT_SECONDS` 限制。
- 营销 Qwen 超时、异常、JSON 解析失败或 schema 校验失败时，使用 `_fallback_marketing_copy`，step 标记 `fallback_used` 并继续后续流程。
- `09_report_prep` 在调用 Qwen 前先生成 deterministic Markdown fallback；Qwen 超时、异常、JSON 解析失败或 unsafe content 时，持久化 fallback Markdown/HTML 报告，step 标记 `fallback_used`。
- 如果报告持久化前发生非 Qwen 的不可恢复错误，workflow state 会写入指向 `/reports?analysis_id={id}` 的 retry entry，`09_report_prep` 标记 `fallback_used`，analysis 可以结束。
- `/api/reports/generate` 的 Qwen timeout 返回 HTTP 200，并持久化 deterministic Markdown/HTML 报告。
- `/api/reports/generate` 的不可恢复错误返回结构化 `REPORT_GENERATION_FAILED`，message 为 `报告生成失败，可重新生成报告。`，避免未处理 500。
- `/reports` 与 `/reports/{id}` 重新生成失败时展示“可重新生成报告”，并保留 regenerate button。
- `DashboardService` 仍只依赖 `AnalysisRun`、`OpportunityScore`、`Product` 与 workflow state，不需要 report rows；现有 `test_dashboard_api_supports_scoring_only_runs` 覆盖 scoring-only 200。

## Prompt Shrink

报告 Qwen prompt 不再传完整 raw provider payload、完整 dashboard payload 或 full score/provider evidence。现在只传 compact payload：

- analysis/company summary
- compact products
- top scores
- core data source lineage
- market/profile summaries
- marketing summaries
- price/content/risk/action notes
- policy notes

Deterministic fallback 仍使用完整 structured input 构造本地报告，保证可查看内容不依赖 Qwen。

## Tests Added

- `backend/tests/test_analysis_workflow.py`
  - report Qwen timeout makes `09_report_prep` `fallback_used`, persists fallback report, records timeout/fallback counts, and completes final analysis.
  - marketing Qwen timeout makes `08_marketing_prep` `fallback_used`, persists fallback marketing assets, records timeout/fallback counts, and completes final analysis.
- `backend/tests/test_report_generation.py`
  - `/api/reports/generate` on Qwen timeout returns 200 with persisted deterministic Markdown/HTML.
  - unrecoverable report-generation error returns structured retryable copy.
- `backend/tests/test_marketing_generation.py`
  - standalone marketing Qwen timeout returns bounded 504 `AI_RESPONSE_TIMEOUT`.

## Verification

- `cd backend && py -3.11 -m pytest tests/test_analysis_workflow.py tests/test_report_generation.py tests/test_marketing_generation.py -q`
  - `24 passed in 6.18s`
- `cd backend && py -3.11 -m pytest tests -q`
  - `304 passed in 16.77s`
- `cd frontend && npm run lint`
  - `No ESLint warnings or errors`
- `cd frontend && npm run build`
  - `Compiled successfully`

## Outcome

`08_marketing_prep` 和 `09_report_prep` 都有明确的默认 Qwen 上限和 deterministic fallback。生产中的默认分析不应再因为 `09_report_prep` Qwen 报告生成慢而无限保持 `running`；完成态会落到 `success` 或 `fallback_used`。
