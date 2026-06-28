# 开发任务看板

状态枚举：`not_started`、`in_progress`、`blocked`、`done_local`、`blocked_production_validation`、`blocked_deploy`、`done`。

状态说明：`done_local` 表示代码或文档已在本地/主分支完成并通过本地验证，但尚未完成生产上线验收；`blocked_production_validation` 表示生产验收被未部署路由阻塞；`blocked_deploy` 表示部署执行本身被阻塞。

并行规则：普通任务线程只写自己的 `docs/status/*_*.md` 状态文件；`agent.md` 和 `docs/TASK_BOARD.md` 由总控线程合并。不得读取、复制或输出本地敏感凭据文件内容。

## 当前真实状态

- 主分支已包含 Q40-Q53 的大量代码、文档和状态文件，Q41-Q51 已完成本地实现与本地验证记录，Q53 已完成演示/部署文档更新。
- 生产环境 `https://opc.ankangyu.cn` 尚未部署 Q42、Q44-Q45、Q47-Q51 等新增路由和页面，生产仍返回多项 404。
- Q52 端到端验收不是完成态，当前状态为 `blocked_production_validation`；必须在生产部署新路由后重跑。
- Q54 生产部署与升级验收不是完成态，当前状态为 `blocked_deploy`；必须先恢复 SSH 或部署流水线，再执行部署并重跑生产验收。
- 后续任务应优先完成部署和验收，不开发新功能，避免继续扩大代码与生产环境的状态差距。

## 已完成任务

| 任务 | 名称 | 状态 | 状态文件 | 完成说明 |
| --- | --- | --- | --- | --- |
| T00 | 总控文档初始化 | done | `docs/status/T00_documentation_init.md` | 创建总控文档、架构、安全规范、任务看板、API 数据源说明和状态目录。 |
| T01 | 项目脚手架 | done | `docs/status/T01_project_scaffold.md` | 创建 Next.js、FastAPI、Docker Compose、`.env.example`、README 和基础页面/API。 |
| T02 | 数据库模型与迁移基础 | done | `docs/status/T02_database_models.md` | 完成 SQLAlchemy 模型、Alembic、基础 CRUD、公司/产品 API。 |
| T03 | Demo 样本数据与 CSV 导入 | done | `docs/status/T03_seed_data_import.md` | 完成种子 CSV、导入服务和导入 API，作为 CSV fallback 基础。 |
| T04 | 阿里云百炼统一调用服务 | done | `docs/status/T04_bailian_integration.md` | 完成 Bailian/DashScope `qwen3.6-plus` 后端接入。 |
| R05 | API 状态纠正、任务重排与安全修正 | done | `docs/status/R05_api_realignment_corrected.md` | 修正文档、`.gitignore`、能力矩阵和敏感文件忽略规则。 |
| R06 | World Bank 与 GDELT provider | done | `docs/status/R06_worldbank_gdelt_providers.md` | 完成无 Key 宏观指标、新闻趋势 provider 和 seed fallback。 |
| R07 | YouTube Data API provider | done | `docs/status/R07_youtube_provider.md` | 完成 YouTube 后端 provider、配置开关和 sample fallback。 |
| R08 | Etsy Open API provider | done | `docs/status/R08_etsy_provider.md` | 完成 Etsy 后端 provider、配置开关和竞品样本 fallback。 |
| R09 | UN Comtrade 双模式接入 | done | `docs/status/R09_un_comtrade_dual_mode.md` | 完成 no-key-first 与可选 Key 双模式，失败回落贸易样本。 |
| R10 | Demo seed data upgrade | done | `docs/status/R10_demo_seed_data_upgrade.md` | 扩充演示样本数据，补齐内容、竞品、贸易和讨论数据。 |
| R11 | 前端 UI realignment | done | `docs/status/R11_frontend_realigned_ui.md` | 完成前端信息架构、导航和基础组件重排。 |
| R12 | 企业与产品管理模块 | done | `docs/status/R12_company_product_module.md` | 完成企业/产品页面、typed API client 和导入交互。 |
| R13 | 数据源能力状态页 | done | `docs/status/R13_provider_status_page.md` | 完成 provider 状态 API、测试 API 和管理页，安全展示配置状态。 |
| R14 | 数据源服务、缓存与调用日志 | done | `docs/status/R14_data_source_service_cache_logs.md` | 完成数据源服务抽象、缓存、调用日志和相关 API。 |
| R15 | 市场与内容分析服务 | done | `docs/status/R15_market_content_analysis.md` | 完成市场画像、内容趋势和数据源融合分析。 |
| R16 | 竞品与机会评分模型 | done | `docs/status/R16_competitor_scoring_model.md` | 完成竞品分析、机会评分和 AI/fallback 解释。 |
| R17 | 出海洞察智能体工作流 | done | `docs/status/R17_agent_workflow.md` | 完成分析运行编排、步骤日志、状态查询和结果持久化。 |
| R18 | 智能体运行页 | done | `docs/status/R18_agent_run_page.md` | 完成 `/analysis/run` 前端主流程、轮询和完成跳转。 |
| R19 | 洞察看板与 ECharts 图表 | done | `docs/status/R19_dashboard_charts.md` | 完成分析详情看板、图表组件和 dashboard API 展示。 |
| R20 | 营销文案生成工作流 | done | `docs/status/R20_marketing_generation.md` | 完成营销文案生成 API、前端页面和结果保存。 |
| R21 | 出海报告生成 | done | `docs/status/R21_report_generation.md` | 完成报告生成 API、列表、详情和预览；PDF 导出保留为 v1 待办。 |
| Q01 | 总控状态同步 | done | `docs/status/Q01_project_consistency_audit.md` | 同步总控文档、项目状态总结和一致性审计。 |
| Q10 | 智能商品导入需求重排与数据模型设计 | done | `docs/status/Q10_product_intake_spec.md` | 完成智能商品导入规格、数据模型设计、AI JSON 契约、合规边界和后续任务重排。 |

## 下一阶段任务

| 任务 | 名称 | 优先级 | 状态 | 依赖 | 主要产出 |
| --- | --- | --- | --- | --- | --- |
| Q02 | 真实 API 冒烟测试与缓存绕过 | P0 | not_started | Q01 | 安全验证 live API、缓存绕过参数、provider 状态与失败回落路径。 |
| Q03 | 安全加固、Admin 保护与密钥扫描 | P0 | not_started | Q01 | Admin 保护方案、密钥扫描记录、前端不泄露凭据验证。 |
| Q04 | Demo 主流程体验修复 | P0 | not_started | Q01 | 企业、产品、分析、看板、营销、报告主流程体验修复清单。 |
| Q05 | CI、依赖审计与构建稳定性 | P0 | not_started | Q01 | CI/check 脚本、依赖审计、build 稳定性记录。 |
| Q06 | 腾讯云生产部署配置 | P0 | not_started | Q03、Q05 | CVM、Docker Compose、Nginx、环境变量和部署运行配置。 |
| Q07 | 一键 Demo 数据与演示流程固化 | P0 | not_started | Q04、Q06 | 一键导入数据、演示脚本、现场兜底流程和操作顺序。 |
| Q08 | 比赛材料和最终交付清单 | P0 | not_started | Q02-Q07 | 路演材料、最终交付清单、风险说明和验收记录。 |
| Q11 | 截图上传与视觉分析后端 | P0 | not_started | Q10、Q03 | 图片上传 API、文件校验、资产记录、Qwen 视觉调用、失败处理和截图回退提示。 |
| Q12 | 国内商品链接解析后端 | P0 | not_started | Q10、Q03 | 单链接解析 API、平台识别、URL 安全校验、公开页面基础信息提取、失败回退截图上传。 |
| Q13 | 产品草稿与确认入库后端 | P0 | not_started | Q10-Q12 | Product Intake 数据表迁移、草稿 CRUD、确认入库、拒绝草稿和审计状态。 |
| Q14 | 前端智能导入页面 | P0 | not_started | Q11-Q13、R12 | 截图上传、链接粘贴、导入任务状态、草稿编辑确认 UI 和风险提示。 |
| Q15 | 接入现有分析流程 | P1 | not_started | Q13、Q14、R17-R21 | confirmed product 进入现有分析、看板、营销和报告流程。 |
| Q16 | 测试、部署和演示材料更新 | P1 | not_started | Q11-Q15、Q06-Q08 | 后端/前端测试、环境变量说明、演示脚本、部署说明和合规风险话术。 |

## 下一轮产品升级任务 Q40-Q54

| 任务 | 名称 | 优先级 | 状态 | 依赖 | 并行关系 | 主要产出 |
| --- | --- | --- | --- | --- | --- | --- |
| Q40 | 产品升级需求与架构重排 | P0 | done | Q39 | 总控文档任务 | 更新项目简介、架构、任务板，新增产品升级规格、插件借鉴评估、第三方 notice 和 Q40 状态记录。 |
| Q41 | 产品升级数据库模型 | P0 | done_local | Q40 | 已完成 | 多图商品、企业拍照、目标国家、全局聊天、报告版本和 proposal 数据模型及迁移；状态文件：`docs/status/Q41_upgrade_database_models.md`。 |
| Q42 | 多图商品录入后端 | P0 | done_local | Q41 | 已完成 | 多图上传、图片角色、AI 多图/单图 fallback、草稿证据和确认链路后端；状态文件：`docs/status/Q42_multi_image_product_intake_backend.md`。 |
| Q43 | 多图商品录入前端 | P0 | done_local | Q42 | 已完成 | 多图选择、预览、排序、删除、角色、主图和草稿证据 UI；状态文件：`docs/status/Q43_multi_image_product_intake_frontend.md`。 |
| Q44 | 后端目标国家与市场区域目录 | P0 | done_local | Q41 | 已完成 | 19 国目标市场目录、预设组合、CSV fallback、分析校验和 provider 映射；状态文件：`docs/status/Q44_target_country_catalog_backend.md`。 |
| Q45 | 目标国家选择前端 | P0 | done_local | Q44 | 已完成 | 分析页动态国家目录、区域/预设选择、国家数量校验和看板国家展示；状态文件：`docs/status/Q45_target_country_selection_frontend.md`。 |
| Q46 | 前端整体信息架构与视觉优化 | P1 | done_local | Q40 | 已完成 | 导航、状态组件、首页、看板、报告、聊天入口和响应式审查；状态文件：`docs/status/Q46_frontend_overall_polish.md`。 |
| Q47 | 企业拍照录入后端 | P0 | done_local | Q41 | 已完成 | 企业图片上传、`company_drafts`、隐私过滤、草稿更新/拒绝/确认入库后端；状态文件：`docs/status/Q47_company_photo_intake_backend.md`。 |
| Q48 | 企业拍照录入前端 | P0 | done_local | Q47 | 已完成 | `/companies/import` 移动端拍照上传、多图预览、企业草稿编辑和确认入库 UI；状态文件：`docs/status/Q48_company_photo_intake_frontend.md`。 |
| Q49 | 全局聊天后端 | P0 | done_local | Q41 | 已完成 | 会话式 `/api/chat`、上下文解析、脱敏裁剪和报告修改 proposal 生成；状态文件：`docs/status/Q49_global_chat_backend.md`。 |
| Q50 | 全局聊天前端 | P0 | done_local | Q49 | 已完成 | 全局悬浮聊天窗口、上下文 ID 白名单、角色切换、快捷问题和安全错误态；状态文件：`docs/status/Q50_global_chat_frontend.md`。 |
| Q51 | 聊天报告修改与版本管理 | P0 | done_local | Q49-Q50 | 已完成 | proposal 确认/拒绝、append-only `report_versions`、旧版本恢复和报告详情版本列表；状态文件：`docs/status/Q51_chat_report_edit_versions.md`。 |
| Q52 | 端到端验收与安全回归 | P0 | blocked_production_validation | Q42-Q51 | 生产阻塞 | 本地回归通过，但生产缺少多图商品、企业拍照、市场目录、全局聊天和报告版本路由；部署后必须重跑。 |
| Q53 | 演示数据、文案与比赛材料更新 | P1 | done_local | Q52 | 文档已完成，生产验收仍阻塞 | 更新 README、部署文档、演示脚本、评委 Q&A、生产 compose 和部署脚本；状态文件：`docs/status/Q53_upgrade_docs_competition_update.md`。 |
| Q54 | 生产部署与升级验收记录 | P0 | blocked_deploy | Q52-Q53 | 部署阻塞 | SSH/部署流水线不可用，生产未升级到 Q40-Q53；恢复部署能力后执行部署并重跑 Q54。 |

## Q 阶段顺序

1. Q01 先完成总控状态同步，消除任务板和实际状态漂移。
2. Q02-Q05 可并行推进，分别处理真实 API、安全、主流程体验和质量稳定性。
3. Q06 在安全和构建稳定性确认后推进生产部署配置。
4. Q07 在主流程体验稳定后固化 Demo 数据和演示步骤。
5. Q08 最后整理比赛材料和最终交付清单。
6. Q10 是智能商品导入需求变更的总控设计任务，不创建迁移或运行时代码。
7. Q11-Q13 在 Q10 后拆分推进后端截图、链接和草稿确认能力；Q14 在接口稳定后实现前端页面。
8. Q15 把确认后的产品接入既有分析、营销和报告流程；Q16 汇总测试、部署和演示材料，并同步影响 Q07/Q08 的最终演示内容。
9. Q40 是下一轮产品升级的总控文档任务，只更新需求、架构、规格、任务板和状态记录，不改业务代码。
10. Q41、Q43、Q44 可在 Q40 后并行推进，分别处理多图商品、拍照企业和目标市场目录后端基础。
11. Q42 依赖 Q41，Q45 依赖 Q44，Q46-Q48 建立全局聊天和报告解析基础。
12. Q49-Q50 在报告解析后实现 proposal 和版本管理；聊天修改报告只生成 proposal，用户确认后才保存新版本。
13. Q51 可与 Q41-Q50 并行做前端体验重排，但不得绕过后端目录、草稿确认和 proposal 确认规则。
14. Q52/Q54 当前均为阻塞态：必须先部署当前主分支到生产，再重跑端到端验收和生产升级验收；在此之前不要继续开发新功能。
15. Q40-Q54 参考 `openai/role-specific-plugins` 时只借方法，不复制插件实现、`.app.json`、connector app id、MCP 配置、assets、scripts、templates、品牌素材或 workspace 绑定；逐项评估见 `docs/ROLE_PLUGIN_ADAPTATION_PLAN.md`。

## 状态文件要求

每个任务完成后创建独立状态文件，例如：

```text
docs/status/Q02_real_api_smoke.md
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
