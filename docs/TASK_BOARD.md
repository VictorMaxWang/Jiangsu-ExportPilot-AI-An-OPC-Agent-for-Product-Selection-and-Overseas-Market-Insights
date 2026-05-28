# 开发任务看板

状态枚举：`not_started`、`in_progress`、`blocked`、`done`。

并行规则：普通任务线程只写自己的 `docs/status/Rxx_*.md` 状态文件；`agent.md` 和 `docs/TASK_BOARD.md` 由总控线程合并。不得读取、复制或输出本地敏感凭据文件内容。

## 已完成任务

| 任务 | 名称 | 状态 | 负责人线程 | 完成说明 |
| --- | --- | --- | --- | --- |
| T00 | 总控文档初始化 | done | 主控开发 Agent | 已创建总控文档、架构、安全规范、任务看板、API 数据源说明和状态目录。 |
| T01 | 项目脚手架 | done | T01 项目脚手架开发 Agent | 已创建 Next.js、FastAPI、Docker Compose、`.env.example`、README 和基础页面/API。 |
| T02 | 数据库模型与迁移基础 | done | T02 数据库模型与迁移开发 Agent | 已完成 SQLAlchemy 模型、Alembic、基础 CRUD、公司/产品 API。 |
| T03 | Demo 样本数据与 CSV 导入 | done | T03 CSV 导入开发 Agent | 已完成种子 CSV、导入服务和导入 API，作为 CSV fallback 基础。 |
| T04 | 阿里云百炼统一调用服务 | done | T04 Bailian 接入开发 Agent | 已完成 Bailian/DashScope `qwen3.6-plus` 后端接入，优先读取 `DASHSCOPE_API_KEY`。 |

## 2026-05-27 API 状态纠正后的任务

| 任务 | 名称 | 优先级 | 状态 | 依赖 | 主要产出 |
| --- | --- | --- | --- | --- | --- |
| R05 | API 状态纠正、任务重排与安全修正 | P0 | done | T00-T04 | 修正文档、更新 `.gitignore`、新增能力矩阵和 R05 状态文件。 |
| R06 | 产品/企业前端工作流补齐 | P0 | not_started | T01、T02 | 前端 API client、企业/产品录入和列表交互。 |
| R07 | 配置状态 API 与管理页 | P0 | not_started | T01、T04、R05 | 后端配置状态 API 与前端管理页，仅显示 configured/not_configured/public。 |
| R08 | 外部数据源抽象层 | P0 | not_started | T02、T03、R05 | 统一 provider 接口、超时、重试、错误类型和 fallback 协议。 |
| R09 | World Bank 数据源 | P0 | not_started | R08 | 无 Key 宏观指标客户端、标准化输出和测试。 |
| R10 | GDELT 数据源 | P0 | not_started | R08 | 无 Key 新闻/舆情客户端、标准化输出和测试。 |
| R11 | YouTube Data API v3 真实接入 | P0 | not_started | R08、R07 | 后端 YouTube 客户端，使用 `YOUTUBE_DATA_API_KEY`，支持 fallback。 |
| R12 | Etsy Open API 真实接入 | P0 | not_started | R08、R07 | 后端 Etsy 客户端，使用 `ETSY_KEYSTRING` 和必要的 `ETSY_SHARED_SECRET`，支持 fallback。 |
| R13 | UN Comtrade 双模式接入 | P1 | not_started | R08 | no-key-first 客户端，可选 `UN_COMTRADE_API_KEY`，非阻塞增强。 |
| R14 | 市场机会评分服务 | P0 | not_started | R09-R12、T04 | 融合 P0 数据源、CSV fallback 和 AI 解释的评分服务。 |
| R15 | 洞察看板与 ECharts 图表 | P0 | not_started | R06、R14 | 市场评分、趋势、国家对比和数据源信号图表。 |
| R16 | 营销文案生成工作流 | P0 | not_started | R06、T04、R14 | 文案生成 API、前端展示和结果保存。 |
| R17 | 出海报告生成与导出 | P0 | not_started | R14、R15、R16 | 报告生成 API、预览页和导出方案。 |
| R18 | CSV fallback 演示闭环 | P0 | not_started | T03、R14 | 样本说明、fallback 路径、导入批次或演示兜底补齐。 |
| R19 | 端到端 Demo 脚本 | P0 | not_started | R15-R18 | 比赛演示数据固化、操作脚本和可复现流程。 |
| R20 | 测试与质量检查 | P0 | not_started | R06-R19 | 后端/前端核心测试、lint、build、集成验证。 |
| R21 | 部署文档与运行指南 | P0 | not_started | R07、R20 | Docker Compose、Nginx、腾讯云 CVM 和环境变量配置指南。 |
| R22 | eBay future provider | P2 | not_started | R08 | eBay 后续扩展接口设计，不阻塞 MVP。 |
| R23 | Rakuten future provider | P2 | not_started | R08 | Rakuten 后续扩展接口设计，不阻塞 MVP。 |
| R24 | Reddit future provider | P2 | not_started | R08 | Reddit 后续扩展接口设计，不阻塞 MVP。 |
| R25 | 比赛最终交付整理 | P0 | not_started | R19-R21 | 交付清单、风险说明、Demo 路演材料和最终验收记录。 |

## 并行顺序

1. 第 1 波：R05 必须先完成，作为后续计划和安全基线。
2. 第 2 波：R06、R07、R08 可并行，分别处理前端工作流、配置状态和 provider 抽象层。
3. 第 3 波：R09、R10、R11、R12 可并行；R13 可同步启动但不阻塞 MVP。
4. 第 4 波：R14 在 P0 数据源具备标准化输出后启动。
5. 第 5 波：R15、R16 可并行，分别做看板和文案工作流。
6. 第 6 波：R17、R18、R19、R20 按功能完成情况增量推进。
7. 第 7 波：R21、R22、R23、R24 可并行，其中 R22-R24 为 P2 后续扩展。
8. 第 8 波：R25 最后完成比赛交付整理。

## 状态文件要求

每个任务完成后创建独立状态文件，例如：

```text
docs/status/R11_youtube_integration.md
```

状态文件必须包含：

- 任务编号与名称
- 负责人线程
- 开始与完成时间
- 修改路径
- 验证命令与结果
- 是否引入环境变量
- 是否影响安全策略
- Blockers 与 follow-up

状态文件不得写入真实 Key、Secret、Token、Cookie、认证头或完整敏感连接串。
