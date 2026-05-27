# 开发任务看板

状态枚举：`not_started`、`in_progress`、`blocked`、`done`

并行规则：后续任务线程不要直接修改本文件；完成后写入 `docs/status/Txx_xxx.md`，由总控线程合并。

## T00 总控文档初始化

- 状态：done
- 目标：建立项目总控文档、开发规范、安全规范、架构说明、任务看板和状态目录。
- 输入：比赛目标、技术栈、数据源列表、安全要求。
- 输出：`AGENTS.md`、`agent.md`、`docs/PROJECT_BRIEF.md`、`docs/ARCHITECTURE.md`、`docs/TASK_BOARD.md`、`docs/SECURITY.md`、`docs/API_SOURCES.md`、`docs/status/`。
- 依赖任务：无。
- 是否可并行：否。
- 主要修改目录：根目录、`docs/`。

## T01 项目脚手架

- 状态：not_started
- 目标：创建 Next.js 前端、FastAPI 后端和基础项目目录。
- 输入：`AGENTS.md`、`docs/ARCHITECTURE.md`。
- 输出：可安装依赖的前后端基础工程。
- 依赖任务：T00。
- 是否可并行：否。
- 主要修改目录：`frontend/`、`backend/`、根目录配置文件。

## T02 Docker Compose

- 状态：not_started
- 目标：提供本地一键启动前端、后端、PostgreSQL 的 Docker Compose 配置。
- 输入：T01 工程结构、环境变量规范。
- 输出：`docker-compose.yml`、Dockerfile、`.env.example`、本地启动说明。
- 依赖任务：T01。
- 是否可并行：部分可并行。
- 主要修改目录：根目录、`frontend/`、`backend/`、`deploy/`。

## T03 数据库模型

- 状态：not_started
- 目标：设计并实现产品、分析请求、数据快照、评分、AI 输出、报告等核心模型。
- 输入：`docs/ARCHITECTURE.md`、MVP 功能范围。
- 输出：SQLAlchemy 模型、迁移方案、基础种子数据接口。
- 依赖任务：T01。
- 是否可并行：可与 T04 部分并行。
- 主要修改目录：`backend/app/models/`、`backend/app/db/`、`backend/tests/`。

## T04 FastAPI 基础

- 状态：not_started
- 目标：实现后端应用入口、健康检查、配置加载、错误处理和基础路由结构。
- 输入：T01 脚手架、T03 初步模型约定。
- 输出：可运行 FastAPI 服务和基础 API。
- 依赖任务：T01。
- 是否可并行：可与 T03 部分并行。
- 主要修改目录：`backend/app/`、`backend/tests/`。

## T05 前端基础布局

- 状态：not_started
- 目标：实现前端全局布局、导航、基础页面框架和 API 客户端雏形。
- 输入：T01 脚手架、项目视觉定位。
- 输出：可访问的首页、产品页、看板页、报告页、管理页框架。
- 依赖任务：T01。
- 是否可并行：可与 T03、T04 并行。
- 主要修改目录：`frontend/app/`、`frontend/components/`、`frontend/lib/`。

## T06 产品录入

- 状态：not_started
- 目标：支持企业手动录入产品信息并保存。
- 输入：T03 数据模型、T04 API 基础、T05 页面框架。
- 输出：产品录入表单、后端产品 API、基础校验。
- 依赖任务：T03、T04、T05。
- 是否可并行：可与 T07 部分并行。
- 主要修改目录：`frontend/features/products/`、`backend/app/api/`、`backend/app/services/`。

## T07 CSV 导入

- 状态：not_started
- 目标：支持上传或导入样例 CSV，完成数据解析、校验和标准化。
- 输入：样例 CSV 格式、T03 模型、T04 API。
- 输出：CSV 导入 API、样例数据、错误提示、fallback 数据记录。
- 依赖任务：T03、T04。
- 是否可并行：可与 T06 部分并行。
- 主要修改目录：`backend/app/services/`、`backend/app/api/`、`data/samples/`、`data/fallback/`。

## T08 外部 API 抽象层

- 状态：not_started
- 目标：定义统一数据源客户端接口、超时、错误处理、标准化输出和 fallback 机制。
- 输入：`docs/API_SOURCES.md`、T04 配置系统、T07 fallback 规则。
- 输出：数据源接口、统一结果类型、基础客户端框架。
- 依赖任务：T04、T07。
- 是否可并行：否。
- 主要修改目录：`backend/app/clients/`、`backend/app/schemas/`、`backend/tests/`。

## T09 World Bank 数据源

- 状态：not_started
- 目标：接入 World Bank 宏观指标，用于国家市场环境分析。
- 输入：T08 数据源抽象、目标国家列表。
- 输出：World Bank 客户端、标准化宏观指标数据。
- 依赖任务：T08。
- 是否可并行：可与 T10、T11、T12 并行。
- 主要修改目录：`backend/app/clients/`、`backend/tests/`。

## T10 GDELT 数据源

- 状态：not_started
- 目标：接入 GDELT 新闻与舆情数据，用于市场关注度和风险信号。
- 输入：T08 数据源抽象、产品关键词、目标市场。
- 输出：GDELT 客户端、新闻趋势和情绪摘要数据。
- 依赖任务：T08。
- 是否可并行：可与 T09、T11、T12 并行。
- 主要修改目录：`backend/app/clients/`、`backend/tests/`。

## T11 电商平台数据源

- 状态：not_started
- 目标：接入 eBay、UN Comtrade、Rakuten、Etsy 等商业与贸易数据源的 MVP 路径。
- 输入：T08 数据源抽象、API Key 配置、CSV fallback。
- 输出：电商与贸易数据客户端、价格/需求/竞争标准化数据。
- 依赖任务：T08。
- 是否可并行：可与 T09、T10、T12 并行。
- 主要修改目录：`backend/app/clients/`、`backend/app/services/`、`backend/tests/`。

## T12 社媒内容数据源

- 状态：not_started
- 目标：接入 YouTube 和 Reddit 内容趋势信号。
- 输入：T08 数据源抽象、API Key 配置、关键词策略。
- 输出：社媒内容客户端、热度、话题和内容样例数据。
- 依赖任务：T08。
- 是否可并行：可与 T09、T10、T11 并行。
- 主要修改目录：`backend/app/clients/`、`backend/app/services/`、`backend/tests/`。

## T13 阿里云百炼封装

- 状态：not_started
- 目标：封装 `qwen3.6-plus` 调用、提示词模板、响应解析和失败处理。
- 输入：阿里云百炼 API 文档、后端配置系统、安全规范。
- 输出：Bailian 客户端、AI 服务、mock/fallback 测试路径。
- 依赖任务：T04。
- 是否可并行：可与 T09-T12 并行。
- 主要修改目录：`backend/app/clients/`、`backend/app/services/`、`backend/tests/`。

## T14 市场机会评分

- 状态：not_started
- 目标：实现市场机会评分模型，融合宏观、贸易、电商、社媒、新闻和 AI 解释。
- 输入：T09-T13 标准化数据。
- 输出：总分、维度分、评分解释、风险提示。
- 依赖任务：T09、T10、T11、T12、T13。
- 是否可并行：否。
- 主要修改目录：`backend/app/services/`、`backend/app/schemas/`、`backend/tests/`。

## T15 营销文案生成

- 状态：not_started
- 目标：基于产品和目标市场生成标题、卖点、广告文案、社媒内容草稿。
- 输入：T06 产品数据、T13 AI 服务、T14 市场洞察。
- 输出：营销文案 API 和前端展示模块。
- 依赖任务：T06、T13、T14。
- 是否可并行：可与 T16 部分并行。
- 主要修改目录：`backend/app/services/`、`frontend/features/copywriting/`。

## T16 可视化看板

- 状态：not_started
- 目标：用 ECharts 展示市场评分、趋势、国家对比和数据源信号。
- 输入：T14 评分结果、T09-T12 数据摘要、T05 页面框架。
- 输出：洞察看板页面和图表组件。
- 依赖任务：T05、T09、T10、T11、T12、T14。
- 是否可并行：可与 T15 部分并行。
- 主要修改目录：`frontend/features/dashboard/`、`frontend/components/charts/`。

## T17 出海报告生成

- 状态：not_started
- 目标：生成结构化出海报告，支持预览和导出。
- 输入：T14 评分、T15 文案、T16 图表数据、T13 AI 服务。
- 输出：报告生成 API、报告预览页、Markdown/HTML/PDF 导出方案。
- 依赖任务：T13、T14、T15、T16。
- 是否可并行：否。
- 主要修改目录：`backend/app/services/`、`frontend/features/reports/`、`data/`。

## T18 管理页与配置状态

- 状态：not_started
- 目标：展示外部 API 和 AI Key 的配置状态，不显示明文。
- 输入：T04 配置系统、`docs/SECURITY.md`。
- 输出：后端配置状态 API、前端管理页。
- 依赖任务：T04、T05。
- 是否可并行：可与 T19 并行。
- 主要修改目录：`backend/app/api/`、`frontend/features/admin/`。

## T19 示例数据与演示脚本

- 状态：not_started
- 目标：准备比赛演示所需的江苏制造产品样例、CSV fallback 和演示流程脚本。
- 输入：MVP 功能、T07 CSV 导入、T14-T17 分析输出。
- 输出：样例数据、演示说明、可复现演示路径。
- 依赖任务：T07、T14、T15、T16、T17。
- 是否可并行：可与 T18、T20 部分并行。
- 主要修改目录：`data/samples/`、`data/fallback/`、`docs/`、`scripts/`。

## T20 测试与质量检查

- 状态：not_started
- 目标：补齐关键测试、类型检查、lint、基础集成验证。
- 输入：T01-T19 代码与文档。
- 输出：测试命令、质量检查结果、修复记录。
- 依赖任务：T01-T19。
- 是否可并行：可在各任务完成后增量进行。
- 主要修改目录：`backend/tests/`、`frontend/`、`docs/status/`。

## T21 部署文档

- 状态：not_started
- 目标：编写腾讯云服务器、Docker Compose、Nginx、环境变量配置和更新流程。
- 输入：T02 部署配置、T18 配置状态、安全规范。
- 输出：部署指南、运维检查清单、回滚说明。
- 依赖任务：T02、T18。
- 是否可并行：可与 T20 部分并行。
- 主要修改目录：`docs/`、`deploy/`。

## T22 比赛交付整理

- 状态：not_started
- 目标：整理比赛提交材料、演示脚本、项目亮点和风险说明。
- 输入：T00-T21 输出。
- 输出：交付清单、路演说明、Demo 操作流程。
- 依赖任务：T00-T21。
- 是否可并行：否。
- 主要修改目录：`docs/`、根目录。
