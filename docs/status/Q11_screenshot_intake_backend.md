# Q11 截图上传与视觉分析后端

## 任务信息

- 任务编号：Q11
- 任务名称：截图上传与视觉分析后端
- 负责人线程：Q11 截图上传与视觉分析后端 Agent
- 开始时间：2026-05-29 15:00:00 +08:00
- 完成时间：2026-05-29 15:28:27 +08:00

## 修改路径

- `backend/requirements.txt`
- `backend/app/core/config.py`
- `backend/app/models/product_intake.py`
- `backend/app/models/__init__.py`
- `backend/app/models/company.py`
- `backend/app/models/product.py`
- `backend/alembic/versions/20260529_0006_create_product_intake_tables.py`
- `backend/alembic/versions/20260528_0004_extend_opportunity_scores_for_r16.py`
- `backend/app/schemas/product_intake.py`
- `backend/app/schemas/__init__.py`
- `backend/app/services/ai/bailian_client.py`
- `backend/app/services/ai/prompts.py`
- `backend/app/services/ai/__init__.py`
- `backend/app/services/product_intake/`
- `backend/app/services/__init__.py`
- `backend/app/api/product_intake/`
- `backend/app/api/router.py`
- `backend/tests/test_product_intake_screenshot_api.py`
- `backend/tests/test_ai_integration.py`
- `docs/status/Q11_screenshot_intake_backend.md`

## 完成内容

- 新增截图导入后端 API：`POST /api/product-intake/screenshot`、`GET /api/product-intake/jobs/{job_id}`、`GET /api/product-intake/drafts/{draft_id}`。
- 新增 `product_import_jobs`、`product_import_assets`、`product_drafts` SQLAlchemy 模型和迁移。
- 新增 `BAILIAN_VISION_ENABLED`、`BAILIAN_VISION_MODEL`、`PRODUCT_UPLOAD_DIR`、`MAX_PRODUCT_IMAGE_SIZE_MB` 后端配置读取。
- 扩展 `BailianClient.vision_chat()`，使用可配置视觉模型，不回退到文本模型。
- 新增截图理解 prompt 和严格 JSON schema 校验。
- 新增截图上传校验：只允许 PNG/JPEG/WebP，按大小限制读取，用 Pillow 校验真实图片、尺寸和像素安全，保存时统一重命名。
- AI 不可用、禁用、超时、非 JSON、schema 错误、低置信度或无法识别产品时，创建低置信度人工草稿，不让接口崩溃。
- 查询响应不返回 `file_path`、原始文件名、base64、`raw_text` 或本地绝对路径。
- 为既有 `20260528_0004` 迁移增加 SQLite 兼容保护：SQLite 下跳过不支持的 `ALTER COLUMN DROP DEFAULT`，PostgreSQL 行为不变。

## 验证命令与结果

- `py -3.11 -m pytest backend/tests/test_product_intake_screenshot_api.py backend/tests/test_ai_integration.py`：通过，25 passed。
- `py -3.11 -m pytest backend/tests`：通过，195 passed。
- `py -3.11 -m alembic -c alembic.ini upgrade head`（在 `backend/` 下，临时 SQLite 数据库）：通过，已运行到 `20260529_0006`。
- `git diff --check`：通过；仅有 Windows 工作区换行提示，无空白错误。

## 安全结果

- 未写入真实 Key、Token、Secret、Cookie 或认证头。
- 测试使用 fake key 和 fake vision client，不访问真实 Bailian/DashScope。
- API 响应只返回安全文件名、MIME、大小、宽高、job/draft 状态和草稿字段。
- 截图 evidence 和错误消息会做基础脱敏与截断，避免手机号、邮箱、长编号、认证头和本地路径进入响应。

## Blockers 与 Follow-up

- Blockers：无。
- Follow-up：Q12/Q13 后续可在现有 `product_drafts` 基础上实现 URL 导入、草稿编辑、确认入正式产品和拒绝草稿。
- Follow-up：生产环境需要在服务器环境变量或部署 Secret 中显式设置 `BAILIAN_VISION_ENABLED=true` 和可用的 `BAILIAN_VISION_MODEL` 后才会发起真实视觉模型调用。
