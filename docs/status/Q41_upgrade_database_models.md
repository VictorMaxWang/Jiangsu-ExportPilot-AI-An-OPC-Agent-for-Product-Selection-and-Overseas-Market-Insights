# Q41 Upgrade Database Models

- 任务编号与名称：Q41 多图商品录入、企业拍照录入、国家库、全局聊天、报告版本管理数据库模型
- 负责人线程：Codex Q41 upgrade database models thread
- 开始时间：2026-06-05 08:01:59 +08:00
- 完成时间：2026-06-05 08:01:59 +08:00
- 状态：done

## Summary

本次任务为产品升级主线补齐数据库基础，不实现新 API 或前端流程。
实现内容包括：

- 扩展 `product_import_assets` 和 `product_drafts`，支持多图顺序、图片角色、主图、图片数量和多图摘要。
- 新增企业拍照录入模型：`company_import_jobs`、`company_import_assets`、`company_drafts`。
- 新增后端国家库模型：`target_countries`、`analysis_country_presets`。
- 新增全局聊天模型：`chat_sessions`、`chat_messages`。
- 新增报告版本和修改 proposal 模型：`report_versions`、`report_edit_proposals`，并为 `reports` 增加 `current_version_id`。
- 报告创建服务会为新报告创建 `report_versions.version_number=1`，保留现有 `reports.content_markdown` 和 `reports.content_html` 兼容旧 API。

## Changed Paths

- `backend/app/models/product_intake.py`
- `backend/app/models/company_intake.py`
- `backend/app/models/target_market.py`
- `backend/app/models/chat.py`
- `backend/app/models/report.py`
- `backend/app/models/company.py`
- `backend/app/models/__init__.py`
- `backend/app/schemas/product_intake.py`
- `backend/app/schemas/company_intake.py`
- `backend/app/schemas/target_markets.py`
- `backend/app/schemas/chat.py`
- `backend/app/schemas/reports.py`
- `backend/app/schemas/__init__.py`
- `backend/app/services/product_intake/screenshot_analyzer.py`
- `backend/app/services/report_service.py`
- `backend/alembic/versions/20260604_0008_q41_upgrade_database_models.py`
- `backend/tests/test_upgrade_database_models.py`
- `docs/status/Q41_upgrade_database_models.md`

## Verification

| Command | Result |
| --- | --- |
| `py -3.11 -m pytest tests\test_upgrade_database_models.py -q` | Passed: 5 passed |
| Temp SQLite `py -3.11 -m alembic upgrade head` | Passed: migration chain reached `20260604_0008` |
| Temp SQLite `py -3.11 -m alembic upgrade head` then `py -3.11 -m alembic downgrade base` | Passed: Q41 upgrade and downgrade completed |
| `py -3.11 -m pytest tests -q` | Passed: 315 passed |

## Environment Variables

No new environment variables were introduced.

## Security Notes

- 未复制或接入 role-specific plugin 代码、assets、scripts、templates、MCP 配置、connector app id、`.app.json` 或 workspace 绑定。
- 新增图片资产 read schema 不回显本地 `file_path`。
- 聊天与 proposal 模型只保存受控上下文引用和脱敏内容字段，不设计高影响写操作绕过确认链路。
- 报告修改仍通过 proposal 和版本链路建模，未覆盖旧版本内容。
- 未读取、写入或输出真实 Key、Cookie、认证头、管理密码、完整敏感连接串或环境文件内容。

## Follow-up

- Q42/Q43 后续可基于本次模型实现多图商品录入和企业拍照录入 API。
- Q44/Q45 后续需要填充国家库数据并把分析请求接入后端目录校验。
- Q46-Q50 后续需要实现全局聊天、报告解析、proposal 确认和版本列表 API。
