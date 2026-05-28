# 苏品智航 / Jiangsu ExportPilot 总控文档

## 项目目标

面向江苏制造企业出海，开发一个 AI 选品与海外市场洞察平台。系统支持企业产品录入、CSV 样本数据导入、公开 API 数据源接入、阿里云百炼 `qwen3.6-plus` 分析、市场机会评分、营销文案生成、可视化看板和出海报告生成。

## 当前总状态

- 当前阶段：`T00-T04`、`R05-R21` 已完成；`Q01` 总控状态同步完成后进入 `Q02-Q08` 收敛阶段。
- 当前已完成闭环：工程脚手架、数据库模型、CSV 导入、Bailian 后端接入、P0/P1 数据源 provider、企业/产品管理、数据源状态页、分析工作流、看板图表、营销文案和报告生成。
- 当前真实数据源：Bailian、World Bank、GDELT、YouTube、Etsy、UN Comtrade；其中 YouTube/Etsy/UN Comtrade 的实时调用取决于后端环境变量、第三方接口状态和配额。
- 当前 fallback：`data/seed/*` 样本数据、CSV fallback、AI sample/mock 文本兜底。缺 Key、禁用、限流、网络失败或第三方异常时必须保持可演示。
- 总控规则：`agent.md` 和 `docs/TASK_BOARD.md` 由总控线程统一合并；普通任务线程只写自己的 `docs/status/*_*.md`。
- 安全基线：真实 API Key 只能进入本机 `.env`、部署 Secret 或服务器环境变量，不得进入代码、文档、测试、README、前端、日志或报告。

## 当前数据源策略

### P0/P1 已接入

- Alibaba Cloud Bailian `qwen3.6-plus`：T04 已完成后端统一调用服务，后端优先读取 `DASHSCOPE_API_KEY`，兼容 `BAILIAN_API_KEY`。
- World Bank Indicators API：R06 已接入，无需 Key；失败时从 `data/seed/market_profiles.csv` 生成宏观指标 fallback。
- GDELT：R06 已接入，无需 Key；失败时从 `data/seed/content_trends.csv` 生成新闻/内容趋势 fallback。
- YouTube Data API v3：R07 已完成后端接入；真实可用性由后端配置状态接口判断，缺 Key、禁用、失败或限流时使用 `data/seed/content_trends.csv` 中的 YouTube sample。
- Etsy Open API：R08 已完成后端接入；真实可用性由后端配置状态接口判断，缺 Key、禁用、失败或限流时使用 `data/seed/competitor_samples.csv` 中的 Etsy sample。
- UN Comtrade：R09 已完成 no-key-first 双模式接入，可选使用后端环境变量；失败时回落 `data/seed/trade_samples.csv`，不得阻塞 MVP 主流程。
- CSV fallback：T03/R10 已完成种子数据和导入能力，是比赛演示兜底路径。

### P2 后续扩展

- eBay、Rakuten、Reddit 仍为 future provider，不作为当前 MVP 阻塞项；不得在文档中暗示已完成 runtime client 或真实调用。

## 开发波次

| 波次 | 目标 | 包含任务 | 当前状态 |
| --- | --- | --- | --- |
| W0 | 总控与工程基础 | T00-T04 | done |
| W1 | API 状态纠正与安全基线 | R05 | done |
| W2 | 数据源、样本数据与基础前端 | R06-R13 | done |
| W3 | 分析、评分与智能体主流程 | R14-R18 | done |
| W4 | 看板、营销与报告闭环 | R19-R21 | done |
| W5 | 总控同步与最终交付收敛 | Q01-Q08 | Q01 done；Q02-Q08 not_started |

## 后续任务

| 任务 | 名称 | 状态 | 目标 |
| --- | --- | --- | --- |
| Q01 | 总控状态同步 | done | 同步总控文档、任务板和项目状态总结，完成一致性审计。 |
| Q02 | 真实 API 冒烟测试与缓存绕过 | not_started | 用安全状态接口和后端调用路径验证 live API 可用性，不读取密钥文件。 |
| Q03 | 安全加固、Admin 保护与密钥扫描 | not_started | 加固后台入口，扫描仓库敏感信息风险，确认前端不暴露 Key。 |
| Q04 | Demo 主流程体验修复 | not_started | 修复比赛演示主路径的体验断点，覆盖企业、产品、分析、看板、营销和报告。 |
| Q05 | CI、依赖审计与构建稳定性 | not_started | 收敛 lint、build、测试、依赖安全与构建超时问题。 |
| Q06 | 腾讯云生产部署配置 | not_started | 固化 CVM、Docker Compose、Nginx、环境变量和部署运行文档。 |
| Q07 | 一键 Demo 数据与演示流程固化 | not_started | 固化可重复导入的数据、演示脚本和现场兜底流程。 |
| Q08 | 比赛材料和最终交付清单 | not_started | 汇总路演材料、交付清单、风险说明和最终验收记录。 |

## 协作规则

- Q 阶段任务使用 `Qxx` 编号，状态文件命名为 `docs/status/Qxx_short_description.md`。
- P0/P1 已完成能力进入维护和验证阶段；P2 future provider 不得阻塞比赛交付。
- 前端只能展示配置状态，不得展示明文、部分明文、哈希、长度或可恢复掩码。
- 本地可能存在 `cross_border_api_keys_and_docs.txt`，任何线程都不得读取、复制或输出其内容。
