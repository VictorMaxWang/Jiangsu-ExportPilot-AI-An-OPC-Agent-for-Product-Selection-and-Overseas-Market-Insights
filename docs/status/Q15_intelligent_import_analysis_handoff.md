# Q15 智能导入接入分析流程

## 任务信息

- 任务编号：Q15
- 任务名称：智能导入产品接入现有分析流程
- 负责线程：Q15 智能导入接入现有分析流程 Agent
- 开始时间：2026-05-29 19:16:00 +08:00
- 完成时间：2026-05-29 20:01:00 +08:00

## 修改路径

- `backend/app/services/agents/export_insight_workflow.py`
- `backend/app/services/scoring/opportunity_scoring.py`
- `backend/app/services/product_intake/draft_review.py`
- `backend/app/services/reports/report_generator.py`
- `backend/tests/test_analysis_workflow.py`
- `backend/tests/test_product_intake_draft_api.py`
- `backend/tests/test_report_generation.py`
- `frontend/app/_lib/api-client.ts`
- `frontend/app/analysis/run/_components/AnalysisRunWorkspace.tsx`
- `frontend/app/products/import/page.tsx`
- `frontend/app/products/import/_components/ProductImportWorkspace.tsx`
- `docs/status/Q15_intelligent_import_analysis_handoff.md`

## 完成内容

- 分析工作流在产品缺少 `product_name_en` 或已存 `ProductKeyword` 时自动调用 `qwen3.6-plus` 关键词生成；成功后写回英文名和英文关键词，失败时使用确定性 fallback 关键词，分析流程继续执行。
- 产品快照和 `workflow_state.product_profiles` 增加 `product_keywords`、`keyword_source`、`generated_keywords`、`intake_source`，保持现有 `/api/analysis/{analysis_id}` 调用方兼容。
- 机会评分 evidence 增加产品关键词和智能导入来源链路，使看板、评分详情和报告读取同一份来源证据。
- confirmed draft 入库描述固定写入“该产品来自用户上传截图/链接，经 AI 提取后由用户确认。”，并保留来源平台、脱敏 URL、证据摘录和识别置信度。
- 报告生成从 `workflow_state` 或 confirmed `ProductDraft` 补齐智能导入来源；AI 报告和 fallback 报告都会包含来源说明，且 URL 去除 query 和 fragment。
- `/analysis/run` 增加“选择最近智能导入产品”区域、低置信度提示和“导入新商品”快捷入口，入口会携带当前 `company_id`。
- `/products/import` 支持 `company_id` 查询参数作为初始企业选择，方便从分析页进入导入流程。

## 验证命令与结果

- `py -3.11 -m pytest tests/test_product_intake_draft_api.py tests/test_analysis_workflow.py tests/test_analysis_api.py tests/test_opportunity_scoring.py tests/test_report_generation.py -q`：通过，27 passed。
- `npx tsc --noEmit`（`frontend/`）：通过。
- `npm run lint`（`frontend/`）：通过，无 ESLint warnings or errors。
- `npm run build`（`frontend/`）：通过，包含 `/analysis/run` 与 `/products/import` 路由构建。
- 浏览器验证（临时前端 `http://127.0.0.1:3009`，临时后端 `http://127.0.0.1:8005`，Playwright + 系统 Chrome）：通过。已验证 `/analysis/run` 出现“选择最近智能导入产品”，“导入新商品”链接为 `/products/import?company_id=1`；模拟 confirmed 低置信度导入草稿后出现精确提示“该产品来自 AI 识别结果，建议确认字段后再分析。”；`/products/import?company_id=1` 初始企业选择值为 `1`。

## Blockers

- 无代码阻塞。Codex in-app Browser 运行时不可用，本轮使用系统 Chrome 的 Playwright 脚本完成页面验证。

## Follow-up

- 当前任务未新增后端路由和数据库迁移；如后续需要在报告模板中更细分截图导入与链接导入，可在现有 `intake_source.source_type` 基础上扩展展示文案。
- 本轮未回退或清理 Q11-Q14 既有未提交改动；后续合并时建议按任务边界分批 review。
