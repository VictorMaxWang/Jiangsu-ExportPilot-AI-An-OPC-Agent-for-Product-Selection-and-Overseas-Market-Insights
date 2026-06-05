# Role Plugin Adaptation Plan

## 目标与总原则

本文件用于 Q40-Q54 产品升级任务的插件借鉴评估。参考对象是 OpenAI `role-specific-plugins` 仓库中的 README、Data Analytics、Sales、Product Design 和 Financial Markets 插件。

本项目不安装、不复制、不接入这些插件。只允许把其中成熟的工作流方法翻译为苏品智航自己的产品需求、API 边界、数据模型、UX 验收和文档标准。

固定原则：

- 只借鉴工作流方法，不复制插件实现、技能原文、脚本、测试、MCP server、runtime widget、assets、templates、品牌素材或 marketplace 元数据。
- 不复制任何 `.app.json` 里的 app id、connector id、OAuth/client id、workspace 绑定或 connector 配置。
- 不把 Sales、Financial Markets 等领域专用术语直接移植为本项目业务概念。
- 所有借鉴都必须落到本项目既有架构：FastAPI、Next.js、PostgreSQL、Qwen、Product Intake、Company Intake、Target Market Catalog、Global Chat、Report Versioning。
- 商品、企业和报告修改继续遵守 draft/proposal/confirm 规则：用户确认前不得写入正式业务对象或覆盖旧版本。

## 可借鉴方法清单

- Data Analytics：来源验证、数据口径、fallback 标记、caveat、报告结构、分析 QA、图表/表格可解释性。
- Sales：草稿、审阅、修改、确认后写入的流程纪律；不借 CRM、pipeline、account、meeting tool 或 outbound workflow。
- Product Design：先确认 brief、基于真实截图/界面证据做 UX 审查、移动端/桌面端状态检查、可访问性风险记录。
- Financial Markets：source posture、事实/假设/推导标签、stale data 与 evidence gap 标记、报告 QC 严谨度；不借投资分析、估值、交易、组合或监管语义。

## Q40-Q54 逐项评估

| 任务 | 是否借鉴 | 借鉴来源 | 可借鉴部分 | 禁止借鉴部分 |
| --- | --- | --- | --- | --- |
| Q40 产品升级需求与架构重排 | 高层方法借鉴 | README、四个插件 README | 记录插件模板的可定制、按角色工作流拆分、connector 需本地替换的原则；作为后续任务的总控边界。 | 不复制插件目录结构、plugin manifest、`.app.json`、MCP 配置、assets、品牌文案或任何工作区绑定。 |
| Q41 多图商品录入后端规格与数据模型 | 不借鉴 | 无 | 仅可参考“证据 ledger”这个通用思想：字段来源、图片资产、置信度、冲突和用户复核要求。 | 不借 Data Analytics 数据仓库模型，不借 Product Design 图片处理脚本，不借插件的文件上传或资产结构；数据模型必须使用本项目 `product_import_jobs`、`product_import_assets`、`product_drafts`。 |
| Q42 多图商品录入前端体验 | 高层方法借鉴 | Product Design | 借 brief 确认、真实界面截图审查、移动端上传体验、错误/空状态、可访问性检查。 | 不复制原型代码、UI 组件、样式、图标、截图编排工具、Figma/Sites 绑定或设计资产。 |
| Q43 拍照新增企业后端与 `company_drafts` | 不借鉴 | 无 | 只保留证据、置信度、隐私过滤、用户确认后入库的通用流程。 | 不借 Sales 的 CRM enrichment、联系人数据、账号画像、外部销售工具或企业数据补全逻辑；企业建档必须按本项目隐私边界实现。 |
| Q44 后端目标国家与市场区域目录 | 不借鉴 | 无 | 可借“语义来源 lane”作为命名方法，把市场目录、provider 映射、fallback 视为后端可控来源。 | 不借插件 connector/source registry、`.app.json`、semantic-layer state 或外部 workspace source 机制；目录必须是本项目数据库和后端 API。 |
| Q45 分析流程接入动态市场目录 | 高层方法借鉴 | Data Analytics | 借来源验证、fallback 标记、口径说明、数据可用性和 caveat 表述。 | 不借数据仓库查询、BI connector、dashboard runtime、semantic layer 或插件校验脚本；国家校验、provider 映射和 fallback 兼容必须本地实现。 |
| Q46 全局聊天后端编排与上下文权限 | 高层方法借鉴 | README、Data Analytics、Sales | 借“上下文路由器”思想：前端传受控 ID，后端解析来源、脱敏摘要、标记缺失来源和权限失败。 | 不复制任何 plugin user-context、preflight 脚本、connector source category、workspace 绑定或外部消息写入逻辑；权限、脱敏、日志策略全部本项目自有。 |
| Q47 全局聊天前端窗口 | 高层方法借鉴 | Product Design、Sales | 借跨页面入口、消息流、proposal 卡片、审阅/修改/确认前置和移动端可用性检查。 | 不借 Sales 外部发送、CRM 更新、邮件/Slack draft 行为；聊天 UI 不得直接覆盖报告或写入正式记录。 |
| Q48 报告解析与引用定位 | 高层方法借鉴 | Data Analytics、Financial Markets | 借报告章节锚点、来源元数据、事实/解释分离、caveat 和 source posture。 | 不借投资报告结构、估值/交易语言、MCP artifact schema、HTML renderer 或报告插件代码；解析器必须针对本项目 Markdown/HTML 报告。 |
| Q49 报告修改 proposal 机制 | 强相关方法借鉴 | Sales、Data Analytics | 借“生成草稿、用户审阅、可继续修改、明确确认后再写入”的流程；借 diff、风险提示、来源引用和 QA 思路。 | 不借 CRM-ready update、邮件/消息发送、外部写入工具或插件状态机原文；`report_edit_proposals` schema、状态、预览 API 由本项目定义。 |
| Q50 报告版本管理与确认保存 | 不借鉴 | 无 | 只保留 append-only history 和 source/proposal 追踪的通用原则。 | 不借 Data Analytics artifact packaging、Financial Markets report package、插件导出工具或外部文档写入；版本表、当前版本指针、回滚策略必须本项目自有。 |
| Q51 前端整体信息架构与视觉优化 | 强相关方法借鉴 | Product Design | 借 brief、流程审查、截图证据、响应式检查、可访问性风险、设计 QA 和真实界面验收方法。 | 不复制 Product Design 原型、视觉方向、品牌色、图标、Sites 发布流程或模板资产；不绕过既有后端 API 契约。 |
| Q52 端到端验收与安全回归 | 高层方法借鉴 | Data Analytics、Product Design、Financial Markets | 借 QA checklist：来源可追溯、关键路径截图、移动端/桌面端、fallback、caveat、报告版本链路和安全边界验证。 | 不借插件测试套件、脚本、MCP validator、artifact renderer 或金融 QC 专用标准；测试必须覆盖本项目实际 API、数据库和 UI。 |
| Q53 演示数据、文案与比赛材料更新 | 高层方法借鉴 | Data Analytics、Product Design、Financial Markets | 借 answer-first 叙事、证据与 caveat 并列、演示路径清晰、风险说明和报告 QC 表述。 | 不借 Sales CRM 话术、投资建议、金融免责声明、插件默认 prompt、示例资产或 marketplace 文案。 |
| Q54 生产部署与升级验收记录 | 不借鉴 | 无 | 只保留 checklist 思维：部署范围、回滚说明、验收记录、未解决风险。 | 不借插件安装、connector 配置、workspace app binding、Node/MCP runtime、外部托管或 marketplace 发布流程；生产部署仍按本项目 Docker/Nginx/腾讯云文档执行。 |

## 后续任务落地要求

- Q41、Q43、Q48、Q49 的规格必须包含 evidence ledger：来源对象、字段、版本或资产引用、置信度、冲突、隐私过滤和用户复核状态。
- Q46、Q47 的聊天链路必须保持“解释与 proposal 生成”定位，不直接执行高影响写操作。
- Q48-Q50 的报告链路必须区分原报告、解析引用、修改 proposal、确认后版本和旧版本保留。
- Q52 的验收必须把“未复制 connector/app id、未复制 `.app.json` workspace 绑定、未引入敏感凭据”作为文档合规检查项。

## 参考来源

- https://github.com/openai/role-specific-plugins
- https://github.com/openai/role-specific-plugins/tree/main/plugins/data-analytics
- https://github.com/openai/role-specific-plugins/tree/main/plugins/sales
- https://github.com/openai/role-specific-plugins/tree/main/plugins/product-design
- https://github.com/openai/role-specific-plugins/tree/main/plugins/financial-markets

