# Q49 Global Chat Backend

- 任务编号与名称：Q49 全局聊天后端
- 负责人线程：Codex Q49 global chat backend implementation thread
- 开始时间：2026-06-05 19:18:00 +08:00
- 完成时间：2026-06-05 19:28:28 +08:00
- 状态：done

## Summary

本次实现后端全局聊天 API，基于既有 `chat_sessions`、`chat_messages`、`report_versions` 和 `report_edit_proposals` 表落地，不新增迁移。

- 新增 `/api/chat/sessions` 会话创建和列表接口。
- 新增 `/api/chat/sessions/{id}/messages` 消息发送和历史读取接口。
- 支持 `page_context`、`report_id`、`analysis_id`、`product_id`，上下文由后端受控解析。
- 聊天提示词借鉴 Data Analytics 的证据/caveat 思路、Sales 的 draft/proposal/confirm 思路、Financial Markets 的事实/假设/缺口/QC 表述纪律，但未复制 connector 配置或插件实现。
- 报告修改请求只创建 `report_edit_proposals(status=draft)`，不覆盖 `reports`，不更新 `current_version_id`，不创建 `report_versions`。
- 增加固定上下文裁剪和脱敏，避免长报告或敏感字段进入提示词、日志和响应。

## Changed Paths

- `backend/app/api/chat.py`
- `backend/app/api/router.py`
- `backend/app/schemas/chat.py`
- `backend/app/schemas/__init__.py`
- `backend/app/services/chat_service.py`
- `backend/app/services/ai/prompts.py`
- `backend/tests/test_global_chat_api.py`
- `docs/status/Q49_global_chat_backend.md`

## Verification

| Command | Result |
| --- | --- |
| `cd backend && py -3.11 -m pytest tests\test_global_chat_api.py -q` | Passed: 5 passed |
| `cd backend && py -3.11 -m pytest tests -q` | Passed: 353 passed |

## Security Notes

- 未读取、写入或输出真实 API Key、Cookie、Token、认证头、数据库 URL 或 `.env` 内容。
- `page_context` 和后端上下文进入提示词前会通过脱敏和长度裁剪。
- Bailian 调用失败时持久化降级助手消息，但错误信息只保留安全错误码和简短说明。
- 报告修改 proposal 需要后续用户确认链路才能进入正式版本，聊天接口不会直接改写报告正文。

## Blockers

- 无。

## Follow-up

- 前端 `/chat` 仍使用旧 `/api/ai/chat` 轻量代理；后续任务可切换到本次新增的会话式 `/api/chat`。
- 后续可补充 proposal 确认、拒绝、版本创建和版本对比 API。
