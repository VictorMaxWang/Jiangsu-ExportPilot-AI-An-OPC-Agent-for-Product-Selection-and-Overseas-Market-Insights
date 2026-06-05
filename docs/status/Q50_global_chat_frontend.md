# Q50 Global Chat Frontend

- 任务编号与名称：Q50 全局聊天前端窗口
- 负责人线程：Codex Q50 global chat frontend implementation thread
- 开始时间：2026-06-05 19:58:00 +08:00
- 完成时间：2026-06-05 20:15:13 +08:00
- 状态：done

## Summary

本次在 Next.js 前端新增全局悬浮聊天入口，入口在所有页面右下角显示；展开后桌面端为右侧停靠面板并给主内容预留安全空间，移动端为可关闭的近全屏面板。

- 新增全局浮窗组件，支持角色切换、快捷问题、中文默认与 EN 切换。
- 前端改用 Q49 会话式 `/api/chat` 后端接口，不再由全局浮窗直接走旧的无会话聊天接口。
- 自动带入白名单上下文 ID：`report_id`、`analysis_id`、`product_id`、`company_id`。
- `page_context` 仅包含页面分组、语言、助手角色和上下文 ID，不包含 DOM 正文、表单字段、报告正文、完整 URL、密钥或用户隐私。
- 错误状态使用非技术化文案，支持显式重试；重试不会自动创建重复可见用户消息。
- 可见 UI 不展示 Qwen、Bailian、FastAPI、Next.js、API 路径、模型名、错误码或堆栈信息。

## Changed Paths

- `docs/status/Q50_global_chat_frontend.md`
- `frontend/app/_components/AppShell.tsx`
- `frontend/app/_components/FloatingChatWidget.tsx`
- `frontend/app/_lib/api-client.ts`
- `frontend/app/_lib/chat-context.ts`

## Verification

| Command / Check | Result |
| --- | --- |
| `cd frontend && npm run lint` | Passed: no ESLint warnings or errors |
| `cd frontend && npm run build` | Passed: Next.js production build completed |
| `cd backend && py -3.11 -m pytest tests\test_global_chat_api.py -q` | Passed: 5 passed |
| Local desktop browser audit at `1366x768` on `http://127.0.0.1:3121/dashboard` | Passed: launcher visible, panel opens, main content safe area not overlapped, no horizontal overflow |
| Desktop interaction audit | Passed: role switch sets `aria-pressed=true`, quick prompt sends, sanitized error appears, retry button appears, Escape closes panel |
| Local mobile browser audit at `390x844` on `/reports?analysis_id=1` | Passed: launcher visible, mobile panel opens, no horizontal overflow, analysis context visible |
| Report detail context audit on `/reports/7` | Passed: report context `报告 #7` visible in chat panel |
| Visible technical-text scan | Passed: floating panel and visible page text did not show Qwen, Bailian, FastAPI, Next.js, API paths, model names, stack traces, or backend error codes |

## Security Notes

- 未读取、写入或输出真实 API Key、Cookie、Token、数据库 URL、认证头或 `.env` 内容。
- 全局聊天前端只向后端传数字 ID 和有限页面元数据。
- 聊天错误文案由前端统一收敛为用户可理解提示，不显示原始异常、路径、模型或服务实现信息。
- 报告修改仍只由后端生成待复核建议，前端本次不新增确认保存或覆盖报告正文的入口。

## Coordination Notes

- 用户本次明确要求创建 `docs/status/Q50_global_chat_frontend.md`。
- 当前 `docs/TASK_BOARD.md` 中旧规划把“全局聊天前端窗口”列为 Q47，把 Q50 留给报告版本管理；本任务按用户指定 Q50 状态文件执行。
- 按 AGENTS.md 协作规则，本实现线程未编辑 `agent.md` 或 `docs/TASK_BOARD.md`。

## Blockers

- 无。

## Follow-up

- `/chat` 独立页面仍保留旧轻量聊天实现；后续可单独切换到会话式 `/api/chat`，但本次未改以降低影响面。
- 本次浏览器审查使用本地前端 dev server；未启动真实本地 FastAPI，因此发送快捷问题时验证的是后端不可用场景下的安全错误与重试 UI。
