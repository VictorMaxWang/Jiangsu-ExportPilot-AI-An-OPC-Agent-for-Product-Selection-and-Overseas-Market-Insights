# Q13 产品草稿校对与确认入库后端

## 任务信息

- 任务编号：Q13
- 任务名称：产品草稿校对、编辑、确认入库与拒绝
- 负责人线程：Q13 产品草稿与确认入库后端 Agent
- 开始时间：2026-05-29 16:20:00 +08:00
- 完成时间：2026-05-29 16:41:17 +08:00

## 修改路径

- `backend/app/api/product_intake/__init__.py`
- `backend/app/services/product_intake/draft_review.py`
- `backend/app/services/product_intake/__init__.py`
- `backend/app/schemas/product_intake.py`
- `backend/app/schemas/__init__.py`
- `backend/tests/test_product_intake_draft_api.py`
- `docs/status/Q13_product_draft_confirm_backend.md`

## 完成内容

- 新增 `GET /api/product-intake/drafts`，支持按 `company_id`、`status`、`source_platform` 查询，并支持 `limit`、`offset` 分页。
- 新增 `PUT /api/product-intake/drafts/{draft_id}`，允许人工编辑草稿业务字段，已确认或已拒绝草稿不可编辑。
- 新增 `POST /api/product-intake/drafts/{draft_id}/confirm`，按请求体 `company_id` 校验归属，将待确认草稿转换为正式 `products` 记录。
- 确认入库时将 `specification`、卖点、目标用户、来源、证据、风险备注和参考价说明写入 `Product.description`；`price_cny` 仅作为参考价，不自动写入采购成本。
- 确认入库时写入 `product_keywords`，来源为 `product_intake_confirmed`，写入 `cross_border_keywords_en` 和 `product_name_en`，并做去重。
- 确认成功后将 `product_drafts.status` 置为 `confirmed`，写入 `confirmed_product_id`，并将对应 `product_import_jobs.status` 置为 `confirmed`。
- 新增 `POST /api/product-intake/drafts/{draft_id}/reject`，拒绝草稿后不创建正式产品，拒绝后不可再确认。
- 新增 Q13 API 测试，覆盖草稿查询、编辑、确认、重复确认、拒绝、关键词持久化、低置信度人工确认和敏感信息不回显。

## 验证命令与结果

- `py -3.11 -m pytest tests/test_product_intake_draft_api.py -q`：通过，8 passed。
- `py -3.11 -m pytest tests/test_product_intake_draft_api.py tests/test_product_intake_screenshot_api.py tests/test_product_intake_url_api.py tests/test_database_api.py tests/test_product_keyword_api.py -q`：通过，35 passed。
- `py -3.11 -m pytest tests -q`：通过，228 passed。

## 安全结果

- 未写入真实 Key、Token、Secret、Cookie 或认证头。
- 确认与拒绝接口通过请求体 `company_id` 校验草稿归属，不匹配时返回 404，避免跨企业确认。
- 草稿编辑文本、拒绝原因、description 组成内容和关键词写入均经过基础清洗与脱敏。
- API 响应不返回 `raw_text`、`file_path`、本地路径、完整敏感 URL、Cookie、Authorization 或 Bearer token。

## Blockers 与 Follow-up

- Blockers：无。
- Follow-up：后续接入真实登录态后，可将 `company_id` 校验替换为认证上下文中的租户范围。
- Follow-up：如需长期防止并发重复关键词，可增加 `product_keywords` 的数据库级唯一约束或函数索引。
