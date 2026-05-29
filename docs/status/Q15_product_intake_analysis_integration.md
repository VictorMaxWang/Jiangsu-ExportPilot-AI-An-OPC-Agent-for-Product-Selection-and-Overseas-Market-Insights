# Q15 智能导入产品接入分析闭环

## 任务信息

- 任务编号：Q15
- 任务名称：智能导入产品接入分析、评分、看板与报告闭环
- 负责线程：Q15 智能导入接入现有分析流程 Agent
- 开始时间：2026-05-29 20:05:00 +08:00
- 完成时间：2026-05-29 20:33:00 +08:00

## 修改路径

- `backend/app/services/agents/export_insight_workflow.py`
- `backend/app/services/scoring/opportunity_scoring.py`
- `backend/app/services/reports/report_generator.py`
- `backend/tests/test_intake_analysis_report_flow.py`
- `backend/tests/test_opportunity_scoring.py`
- `backend/tests/test_report_generation.py`
- `docs/status/Q15_product_intake_analysis_integration.md`

## 完成内容

- confirmed `ProductDraft` 的来源链路继续进入分析工作流、评分 evidence 和报告输入，并补充 `domestic_reference_price_cny`、`domestic_price_role=domestic_reference_only` 与价格边界说明。
- 机会评分保持 `price_score` 基于海外竞品样本价格带；国内截图/链接价格不进入海外价格评分，也不被视为跨境售价或采购成本。
- 对来自淘宝/天猫/拼多多/京东截图或链接且有国内参考价的产品，`supply_score` 仅做小幅产品信息完整度加权。
- 报告强制增加数据源边界说明：
  - 国内商品截图/链接用于识别企业可供产品信息。
  - 海外机会评分仍基于海外竞品样本、内容趋势、国家市场画像与贸易数据。
  - 国内链接价格不代表海外销售价格，不作为海外竞品价格、成交价、采购成本或利润依据。
- 新增端到端后端测试：创建 URL draft、确认成 product、运行 analysis、获取 dashboard、生成/读取 report，并验证报告包含导入来源说明且 URL query token 被移除。

## 验证命令与结果

- `py -3.11 -m pytest tests/test_intake_analysis_report_flow.py tests/test_product_intake_url_api.py tests/test_product_intake_draft_api.py tests/test_analysis_workflow.py tests/test_analysis_api.py tests/test_dashboard_api.py tests/test_opportunity_scoring.py tests/test_report_generation.py -q`：通过，41 passed。
- `npx tsc --noEmit`（`frontend/`）：通过。
- `npm run lint`（`frontend/`）：通过，无 ESLint warnings or errors。
- `npm run build`（`frontend/`）：通过，包含 `/analysis/run` 与 `/products/import` 路由构建。
- `git diff --check`：通过，仅有 Windows 工作区 CRLF 提示，无空白错误。

## Blockers

- 无代码阻塞。

## Follow-up

- 前端当前只展示最近 5 条 confirmed 智能导入产品；如果后续需要覆盖手动勾选较早低置信度导入产品，可让产品列表 API 直接返回 `intake_source.low_confidence` 或增加按产品 ID 查询导入来源的轻量接口。
- 本轮未清理 Q11-Q14 既有未提交改动，也未修改 `docs/TASK_BOARD.md`。
