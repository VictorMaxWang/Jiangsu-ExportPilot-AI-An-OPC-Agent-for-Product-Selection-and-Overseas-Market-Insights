# R17 多智能体工作流后端

- 任务编号与名称：R17 多智能体工作流后端
- Owner thread：R17 新版智能体工作流 Agent
- Start time：2026-05-28T12:20:00+08:00
- End time：2026-05-28T13:35:00+08:00
- Status：done

## 完成内容

- 新增 `ExportInsightWorkflow`，按顺序执行 9 个节点：
  `CompanyProfilingAgent`、`ProductUnderstandingAgent`、`DataCollectionAgent`、`CompetitorAnalysisAgent`、`MarketProfilingAgent`、`ContentTrendAgent`、`OpportunityScoringAgent`、`MarketingPrepAgent`、`ReportPrepAgent`。
- 新增 `/api/analysis/run`、`/api/analysis/{analysis_id}`、`/api/analysis/{analysis_id}/status`。
- `POST /api/analysis/run` 创建 `analysis_runs` 记录，初始化 step logs，并通过 FastAPI background task 执行工作流，适合前端轮询展示。
- `analysis_runs` 新增 `current_step`、`step_logs`、`workflow_state`，用于记录当前步骤、节点状态、评分摘要、provider 汇总、营销准备和报告入口。
- `OpportunityScoringService` 新增 `run_for_analysis()`，可把评分结果写入已存在的 `analysis_run.id`，现有 `/api/scoring/run` 行为保持兼容。
- 外部 API 或 Bailian 失败时使用 CSV fallback、缓存、确定性营销文案和报告模板继续完成 Demo。
- 生成 Markdown 报告并保存到 `reports`，`next_page_url` 固定为 `/reports?analysis_id={analysis_id}`。
- Provider 汇总包含当前真实可用链路：Bailian、World Bank、GDELT、YouTube、Etsy、optional UN Comtrade、CSV fallback。
- eBay、Rakuten、Reddit 未新增客户端、未调用、未写入必需 provider 链路。
- 已按要求使用 subagents 做只读规划检查：workflow-agent、node-agent、fallback-agent、status-api-agent、reviewer-agent。

## Changed Paths

- `backend/alembic/versions/20260528_0005_add_analysis_workflow_state.py`
- `backend/app/api/analysis/__init__.py`
- `backend/app/api/router.py`
- `backend/app/models/analysis.py`
- `backend/app/schemas/analysis.py`
- `backend/app/schemas/__init__.py`
- `backend/app/services/agents/__init__.py`
- `backend/app/services/agents/export_insight_workflow.py`
- `backend/app/services/scoring/opportunity_scoring.py`
- `backend/tests/test_analysis_workflow.py`
- `backend/tests/test_analysis_api.py`
- `docs/status/R17_agent_workflow.md`

## Test Results

```powershell
cd backend
py -3.11 -m compileall app
```

Result：passed。

```powershell
cd backend
py -3.11 -m pytest tests/test_analysis_workflow.py tests/test_analysis_api.py tests/test_opportunity_scoring.py tests/test_opportunity_scoring_api.py -q
```

Result：passed，`14 passed`。

```powershell
cd backend
py -3.11 -m pytest tests -q
```

Result：passed，`143 passed`。

## Security And Fallback Notes

- 未写入真实 API key、token、cookie、数据库密码或第三方密钥。
- API 响应只暴露 provider 名称、fallback 状态、步骤日志和脱敏错误，不暴露上游 headers、URL secret 或原始异常详情。
- Bailian 不可用或输出非法 JSON 时，营销文案和报告引言使用确定性 fallback。
- World Bank、GDELT、YouTube、Etsy、UN Comtrade 失败时通过 `DataSourceService` 使用 CSV fallback，并在 step logs 与 provider summary 中标记。

## Blockers

- None.

## Follow-up Notes

- 当前前端 `/analysis/run` 仍是占位页面；后续可接入 `POST /api/analysis/run` 和 `GET /api/analysis/{analysis_id}/status` 做轮询展示。
- 若未来需要可恢复的长任务队列，可将 background task 升级为独立 worker，但本次 R17 已满足比赛 Demo 的稳定轮询需求。
