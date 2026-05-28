# 苏品智航 / Jiangsu ExportPilot 总控文档

## 项目目标

面向江苏制造企业出海，开发一个 AI 选品与海外市场洞察平台。系统支持企业产品录入、CSV 样本数据导入、公开 API 数据源接入、阿里云百炼 `qwen3.6-plus` 分析、市场机会评分、营销文案生成、可视化看板和出海报告生成。

## 当前总状态

- 当前阶段：T00-T04 已完成，R05 已完成 API 状态纠正与安全修正。
- 当前 MVP 数据源：Bailian + World Bank + GDELT + YouTube + Etsy + CSV fallback。
- 总控规则：`agent.md` 和 `docs/TASK_BOARD.md` 由总控线程统一合并；普通任务线程只写自己的 `docs/status/Rxx_*.md`。
- 安全基线：真实 API Key 只能进入本机 `.env`、部署 Secret 或服务器环境变量，不得进入代码、文档、测试、README、前端、日志或报告。

## 2026-05-27 API 状态纠正记录

### P0 MVP 数据源

- Alibaba Cloud Bailian `qwen3.6-plus`：T04 已完成后端接入，后端优先读取 `DASHSCOPE_API_KEY`，兼容 `BAILIAN_API_KEY`。
- World Bank Indicators API：无需 Key，作为宏观市场指标数据源。
- GDELT：无需 Key，作为新闻热度、舆情和风险信号数据源。
- YouTube Data API v3：用户已获得 API Key，后端通过 `YOUTUBE_DATA_API_KEY` 读取，列为 P0 真实接入任务。
- Etsy Open API：用户确认 Key 可用，后端通过 `ETSY_KEYSTRING` 和必要的 `ETSY_SHARED_SECRET` 读取，列为 P0 真实接入任务。
- CSV fallback：T03 已完成，必须保留为演示兜底路径。

### P1 可选增强

- UN Comtrade：采用 no-key-first 策略，优先无 Key 调用；遇到 401、403 或限额类错误时，再尝试可选 `UN_COMTRADE_API_KEY`。
- UN Comtrade 不得作为 MVP 主流程强依赖；失败时回落 CSV fallback 或跳过增强字段。

### P2 后续扩展

- eBay：暂无 Key，作为 future provider。
- Rakuten：暂无 Key，作为 future provider。
- Reddit：暂无 Key，作为 future provider。

## 开发波次

| 波次 | 目标 | 包含任务 | 预期结果 |
| --- | --- | --- | --- |
| W0 | 总控与工程基础 | T00-T04 | 文档、脚手架、数据库、CSV 导入和 Bailian 接入完成。 |
| W1 | 计划纠正与安全基线 | R05 | API 状态、任务看板、能力矩阵和敏感文件忽略规则完成。 |
| W2 | 核心工作流与数据源基础 | R06-R13 | 产品/企业工作流、配置状态、provider 抽象层和 P0/P1 数据源接入。 |
| W3 | AI 分析与前端呈现 | R14-R18 | 机会评分、看板、文案、报告和 fallback 演示闭环。 |
| W4 | 交付质量与部署 | R19-R25 | Demo 脚本、测试质量、部署文档、P2 扩展设计和最终交付。 |

## 协作规则

- R05 之后新任务使用 `Rxx` 编号，状态文件命名为 `docs/status/Rxx_short_description.md`。
- P0 任务优先服务比赛 MVP；P1 任务不得阻塞 P0；P2 任务只做后续扩展准备。
- YouTube 和 Etsy 是 P0 真实接入任务；eBay、Rakuten、Reddit 不是 MVP 阻塞项。
- 前端只能展示配置状态，不得展示明文、部分明文、哈希、长度或可恢复掩码。
- 本地可能存在 `cross_border_api_keys_and_docs.txt`，任何线程都不得读取、复制或输出其内容。
