# Q04 Demo 主流程体验修复

- 任务 ID：Q04
- 任务名称：Demo 主流程体验修复
- Owner thread：Q04 Demo 主流程体验修复 Agent
- 开始时间：2026-05-28 20:05 +08:00
- 完成时间：2026-05-28 20:37 +08:00

## Changed paths

- `frontend/app/page.tsx`
- `frontend/app/products/_components/ProductsWorkspace.tsx`
- `frontend/app/analysis/run/_components/AnalysisRunWorkspace.tsx`
- `frontend/app/dashboard/page.tsx`
- `frontend/app/dashboard/_components/DashboardDetailWorkspace.tsx`
- `frontend/app/marketing/_components/MarketingWorkspace.tsx`
- `frontend/app/reports/_components/ReportsWorkspace.tsx`
- `frontend/app/reports/_components/ReportDetailWorkspace.tsx`
- `frontend/components/charts/ChartPanel.tsx`
- `docs/status/Q04_demo_flow_polish.md`

## Summary

- 首页 CTA 改为“进入演示流程”和“查看示例报告”。
- 产品页补齐无企业、无产品和关键词生成失败的演示兜底状态。
- 分析运行页改为默认首个企业、前 3 个产品、US/JP/GB，并取消完成后自动跳转，改为显式“查看看板”“生成报告”。
- 看板补充空状态、图表数据源说明、竞品样本免责声明和营销入口。
- 营销页支持按 `analysis_id` 自动选 top recommendation，并优先展示 workflow 中已有营销草稿。
- 报告页补充过滤文案、详情页重新生成报告，以及 PDF 部署版说明。

## Validation

- `cd frontend && npm run lint`：通过，0 warnings/errors。
- `cd frontend && npm run build`：通过，Next.js production build 成功。
- `cd backend && py -3.11 -m pytest tests -q`：通过，177 passed。

## Security and env

- 未新增环境变量。
- 未写入 API key、token、cookie、secret 或真实凭据。
- 未改变后端公开 API 或密钥读取策略。

## Blockers and follow-up

- Blockers：无。
- Follow-up：建议 Q07 固化一键 Demo 数据时，补一个“最近一次 analysis_id”入口，方便从裸 `/dashboard` 直接回到最新看板。
