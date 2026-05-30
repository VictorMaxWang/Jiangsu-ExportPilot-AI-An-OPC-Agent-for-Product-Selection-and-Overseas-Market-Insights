# Q20 i18n zh-CN Default Language Toggle

- Task id: Q20
- Owner thread: Codex
- Start time: 2026-05-30 19:00:29 +08:00
- End time: 2026-05-30 19:19:41 +08:00
- Scope: frontend zh-CN default UI and lightweight language toggle

## Changed Paths

- `frontend/app/_components/AppShell.tsx`
- `frontend/app/_components/LanguageProvider.tsx`
- `frontend/app/_components/LanguageToggle.tsx`
- `frontend/app/_components/PageHeader.tsx`
- `frontend/app/_lib/api-client.ts`
- `frontend/app/_lib/i18n.ts`
- `frontend/app/_lib/navigation.ts`
- `frontend/app/page.tsx`
- `frontend/app/companies/page.tsx`
- `frontend/app/products/page.tsx`
- `frontend/app/products/import/page.tsx`
- `frontend/app/analysis/run/page.tsx`
- `frontend/app/analysis/run/_components/AnalysisRunWorkspace.tsx`
- `frontend/app/dashboard/page.tsx`
- `frontend/app/dashboard/_components/DashboardDetailWorkspace.tsx`
- `frontend/app/marketing/page.tsx`
- `frontend/app/marketing/_components/MarketingWorkspace.tsx`
- `frontend/app/reports/_components/ReportsWorkspace.tsx`
- `frontend/app/reports/_components/ReportDetailWorkspace.tsx`
- `frontend/app/admin/api-keys/page.tsx`
- `frontend/app/admin/data-sources/page.tsx`
- `frontend/app/admin/_components/ProviderStatusDashboard.tsx`
- `frontend/components/agent-flow/AgentFlowTimeline.tsx`
- `frontend/components/agent-flow/index.ts`
- `frontend/components/product-intake/ProductDraftEditor.tsx`
- `docs/status/Q20_i18n_zh_default_language_toggle.md`

## Implementation Notes

- Added a small `zh-CN` / `en` locale helper, a client `LanguageProvider`, and a top-right `中 / EN` toggle in the app shell.
- Default locale is `zh-CN`; the selected locale is persisted in `localStorage` after client hydration.
- Kept the implementation lightweight and did not introduce a large i18n framework.
- Converted covered page headers, navigation, workflow labels, report/admin/marketing/dashboard UI labels, status badges, buttons, notices, and common error messages to Chinese defaults.
- Preserved generated English product titles, SEO keywords, Markdown labels, HTML labels, provider names, and backend enum/type values where they are data or technical identifiers rather than UI copy.

## Validation

- `npm run lint`: passed, no ESLint warnings or errors.
- `npm run build`: passed, production build completed successfully.

## Security Notes

- No backend key handling was changed.
- No keys, cookies, `.env` values, request headers, or passwords were written to this status file.
- Admin password UI remains session-only; frontend does not persist the password.

## Blockers And Follow-Ups

- No implementation blockers.
- English toggle currently localizes the app shell, home page, and major page headers; deeper workflow controls are intentionally Chinese-first for competition review consistency.
