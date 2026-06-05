# Q40 产品升级需求与架构重排

- 任务编号与名称：Q40 产品升级需求与架构重排
- 负责人线程：Codex Q40 product upgrade architecture thread
- 开始时间：2026-06-04 +08:00
- 完成时间：2026-06-04 +08:00
- 状态：done

## Summary

本次 Q40 是文档总控任务，为下一轮产品升级重排需求、架构、规格和任务板，不修改业务代码。

新增升级方向：

- 多图商品录入：多张商品图片先生成 `product_drafts`，用户确认后才写入正式产品库。
- 拍照新增企业：企业资料图片先生成 `company_drafts`，用户确认后才写入正式企业库。
- 目标市场扩展：目标国家由后端 Target Market Catalog 和后端国家库管理，前端不写死国家列表。
- 全局 AI 聊天：聊天窗口可解释分析、解析报告和生成报告修改 proposal。
- 报告版本管理：聊天修改报告只生成 proposal，用户确认后保存新 `report_versions`，原版本保留。
- 插件借鉴评估：逐项评估 Q40-Q54 是否借鉴 `openai/role-specific-plugins`，明确只借工作流方法，不复制插件实现或 connector/workspace 绑定。

## Changed Paths

- `docs/PROJECT_BRIEF.md`
- `docs/ARCHITECTURE.md`
- `docs/TASK_BOARD.md`
- `docs/ROLE_PLUGIN_ADAPTATION_PLAN.md`
- `docs/PRODUCT_UPGRADE_SPEC.md`
- `docs/THIRD_PARTY_NOTICES.md`
- `docs/status/Q40_product_upgrade_architecture.md`

## Verification

| Command | Result |
| --- | --- |
| `git status --short` plus `git diff --name-only` | Passed. Changed paths are limited to Q40 documentation files under `docs/`, including new untracked docs. |
| `rg -n "Q4[0-9]\|Q5[0-4]" docs/ROLE_PLUGIN_ADAPTATION_PLAN.md docs/TASK_BOARD.md` | Passed. Q40-Q54 are present in the adaptation plan and task board. |
| Connector/workspace binding scan across `docs/` | Passed. Matches are policy-only exclusion text; no real connector app id, workspace binding, OAuth/client id or copied `.app.json` content was introduced. |
| Sensitive keyword scan across `docs/` | Passed. Matches are policy-only security terms; no real Key、Cookie、认证头、管理密码、完整敏感连接串或环境文件内容 was found. |
| `git diff -- docs` review | Passed. Diff is documentation-only, UTF-8 Chinese is readable, and MIT License notice is present. |

## Security Notes

- 本任务未读取、复制或输出本地敏感凭据文件内容。
- 本任务未写入真实 Key、Cookie、认证头、管理密码、完整敏感连接串或环境文件内容。
- 本任务未复制 `openai/role-specific-plugins` 的 `.app.json`、connector app id、workspace 绑定、MCP 配置、assets、scripts、templates 或品牌素材。
- 文档只记录未来架构、插件借鉴边界和任务方向，不引入新的环境变量值。

## Follow-up

- Q41、Q43、Q44 可在 Q40 后并行启动，分别推进多图商品录入、企业拍照录入和目标市场目录后端基础。
- Q46-Q50 需要保持聊天、报告 proposal 和版本管理的确认链路，不得让聊天直接覆盖报告正文。
- Q41-Q54 实施时必须先查看 `docs/ROLE_PLUGIN_ADAPTATION_PLAN.md`，确认对应任务只借鉴允许的方法，不复制任何插件实现或 connector/workspace 绑定。
