# 项目状态总结

更新时间：2026-05-28

## 已完成功能

- 工程基础：Next.js 前端、FastAPI 后端、Docker Compose、`.env.example`、README、基础健康检查。
- 数据层：SQLAlchemy 模型、Alembic 迁移、公司/产品 CRUD、CSV 导入服务。
- AI 能力：Bailian/DashScope `qwen3.6-plus` 后端统一调用、prompt 和 JSON 解析兜底。
- 数据源：World Bank、GDELT、YouTube、Etsy、UN Comtrade provider，以及数据源缓存和调用日志。
- 管理能力：provider 状态 API、provider 测试 API、管理页安全展示 configured/not_configured/public/fallback 类状态。
- 业务流程：企业/产品管理、智能体分析运行页、分析状态轮询、看板图表、营销文案生成、出海报告生成。
- 演示数据：`data/seed/` 下产品、市场、内容、竞品、贸易和用户讨论样本。

## 当前真实数据源

- Bailian：后端优先读取 `DASHSCOPE_API_KEY`，兼容 `BAILIAN_API_KEY`；未配置或失败时走 sample/mock AI 文本。
- World Bank：公开 API，无需 Key；失败时读取 `data/seed/market_profiles.csv`。
- GDELT：公开 API，无需 Key；失败时读取 `data/seed/content_trends.csv`。
- YouTube：后端 provider 已接入；真实可用性取决于后端环境变量、第三方状态和额度，失败时读取 YouTube sample。
- Etsy：后端 provider 已接入；真实可用性取决于后端环境变量、第三方状态和额度，失败时读取 Etsy sample。
- UN Comtrade：no-key-first 双模式已接入，可选后端环境变量，失败时读取 `data/seed/trade_samples.csv`。
- eBay、Rakuten、Reddit：当前为 P2 future provider，无 runtime client，不阻塞 MVP。

## 当前 fallback 机制

- `data/seed/market_profiles.csv`：World Bank 宏观指标 fallback。
- `data/seed/content_trends.csv`：GDELT 内容趋势 fallback 和 YouTube sample。
- `data/seed/competitor_samples.csv`：Etsy 竞品 fallback。
- `data/seed/trade_samples.csv`：UN Comtrade 贸易样本 fallback。
- `data/seed/product_catalog.csv`：产品导入和演示产品 fallback。
- `data/seed/user_discussions.csv`：用户讨论、内容洞察和演示补充样本。
- AI fallback：Bailian 未配置或调用异常时使用 sample/mock 文本，并在响应中标记来源。

## 当前测试数量

- Backend：`backend/tests/` 当前有 23 个 `test_*.py` 文件。
- Backend pytest：Q01 当前验证为 157 个测试通过。
- Frontend：当前未发现 `*.test.*` 或 `*.spec.*` 测试文件。
- Frontend lint/build：Q01 当前验证为 `npm run lint` 通过、`npm run build` 通过。

## 当前已知风险

- Q01 未做真实外部 API 冒烟测试；live API 可用性需要 Q02 通过后端安全状态接口和 provider 测试接口确认。
- 产品导入存在两个后端入口：`/api/products/import` 与 `/api/import/products`。当前前端使用 `/api/products/import`，另一路应作为兼容入口或在后续统一。
- 健康检查当前为 `/health`，不是 `/api/health`；若部署网关要求统一 `/api/*`，Q06 需要确认探针策略或补别名。
- `R08/R09/R10/R12/R13` 状态文件缺少显式 `Status: done` 行，但包含完成时间、完成内容和验证结果；Q01 依据状态文件事实判定为 done，未批量改旧状态文件。
- PDF 导出在 R21 中保留为 v1 待办，当前报告能力以生成、列表、详情和预览为主。
- Admin 保护和密钥扫描还未完成，需要 Q03 处理。

## 下一阶段任务

- Q02 真实 API 冒烟测试与缓存绕过。
- Q03 安全加固、Admin 保护与密钥扫描。
- Q04 Demo 主流程体验修复。
- Q05 CI、依赖审计与构建稳定性。
- Q06 腾讯云生产部署配置。
- Q07 一键 Demo 数据与演示流程固化。
- Q08 比赛材料和最终交付清单。
