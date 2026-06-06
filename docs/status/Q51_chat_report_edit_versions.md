# Q51 Chat Report Edit Versions

- Task id: Q51
- Owner thread: Codex desktop thread `019e97c0-ee82-7a5-7608a0fc8c57`
- Start time: 2026-06-05 20:28:01 +08:00
- End time: 2026-06-05 21:13:20 +08:00

## Summary

聊天窗口现在可以针对当前报告生成“只提议、不覆盖”的修改建议。用户在聊天卡片中点击“应用修改”后，后端会追加新的 `report_versions` 版本并更新报告当前指针；点击“拒绝修改”只更新提案状态。报告详情页显示版本列表，并支持以 append-only 方式恢复旧版本。

## Changed Paths

- `backend/app/api/reports/__init__.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/reports.py`
- `backend/app/services/ai/prompts.py`
- `backend/app/services/chat_service.py`
- `backend/app/services/report_quality.py`
- `backend/app/services/report_service.py`
- `backend/tests/test_global_chat_api.py`
- `frontend/app/_components/FloatingChatWidget.tsx`
- `frontend/app/_lib/api-client.ts`
- `frontend/app/reports/_components/ReportDetailWorkspace.tsx`
- `docs/status/Q51_chat_report_edit_versions.md`

## Implementation Notes

- Kept the existing Q41 `report_versions` and `report_edit_proposals` tables; no migration was added.
- Added routes for listing versions, confirming/rejecting proposals, and append-only restore.
- Confirmation creates `source_type="proposal"` report versions, links `source_proposal_id`, marks proposals accepted, and updates `reports.current_version_id`, `content_markdown`, and rendered HTML.
- Restore creates a new `source_type="restore"` version copied from the selected old version instead of moving the current pointer backward.
- Chat report edits now require summary, full markdown draft, and rationale in the prompt contract; assistant messages surface those fields for the user.
- Report QC checks data-source disclosure, fallback/sample disclosure, missing caveats, exaggerated language, real sales claims, GMV claims, and guaranteed sales/conversion claims. Severe unresolved issues block proposal confirmation with `422`.
- Frontend report detail page displays version history with current badges and restore buttons.
- Floating chat renders proposal cards with summary, rationale, markdown draft preview, risk notes, and `应用修改 / 拒绝修改` actions.

## Verification Results

- `cd backend && py -3.11 -m pytest tests -q`: passed, `357 passed in 28.82s`.
- `cd frontend && npm run lint`: passed, no ESLint warnings or errors.
- `cd frontend && npm run build`: passed.
- Browser smoke check with local Next dev server and mocked API responses: passed. Verified report version list, restore button, chat proposal card, `应用修改`, `拒绝修改`, and post-apply `已应用` state.

## Blockers

- None.

## Follow-up Notes

- Playwright package was installed in the project, but bundled Playwright browsers were not present locally. Browser smoke check used the system Chrome executable instead.
- Backend confirmation deliberately renders HTML from the accepted markdown draft instead of trusting AI-supplied HTML.
