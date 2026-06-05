# Q46 UX Audit Report

- Audit date: 2026-06-05 14:03 +08:00
- Product: SuPin ZhiHang / Jiangsu ExportPilot
- Production URL: https://opc.ankangyu.cn
- Method: Product Design live-surface audit approach with Playwright/Chrome DOM and responsive inspection.
- Pages checked: `/`, `/products/import`, `/analysis/run`, `/dashboard`, `/reports`
- Viewports checked: desktop `1366x768`, mobile `390x844`

## Evidence Summary

- No page-level horizontal overflow was detected on the five checked pages at desktop or `390px` mobile widths.
- Current primary navigation exposes `首页 / 企业 / 产品 / 分析 / 看板 / 营销 / 报告 / 能力状态 / 数据源`, but does not expose `智能导入` or `聊天` as first-class entries.
- Homepage first screen still describes the older broad demo flow: `企业产品输入 -> 多源数据融合 -> 智能体分析 -> 机会评分 -> 营销生成 -> 出海报告`.
- `/reports` shows repeated long disabled PDF buttons on each report card, which competes with the real actions: view, copy Markdown, and open dashboard.
- `/dashboard` without `analysis_id` is usable but its empty state does not clearly connect users back to the newer intelligent import to analysis to dashboard/report path.

## High Priority

1. **Primary navigation is crowded and misses key workflow entries.**  
   Evidence: all checked pages show admin/status links in primary navigation, while `/products/import` and chat are not direct top-level entries.  
   Fix: make primary nav `企业 / 产品 / 智能导入 / 分析 / 看板 / 报告 / 聊天`; keep Home on the brand link and move admin/status links into a secondary utility row.

2. **Homepage does not lead with the upgraded intake-to-report workflow.**  
   Evidence: `/` still emphasizes the older six-step workflow and sends the primary CTA to `/analysis/run`.  
   Fix: rewrite first screen around `上传截图/链接 -> Qwen 识别 -> 产品草稿 -> 出海分析 -> 看板/报告`, with primary CTA to `/products/import`.

3. **Reports page action hierarchy is noisy.**  
   Evidence: `/reports` repeats `PDF 导出将在部署版开启；当前支持 Markdown/HTML 报告。` as a disabled button on every card.  
   Fix: replace the long disabled button with compact status badges and keep real actions visually dominant.

4. **Shared success feedback is inconsistent.**  
   Evidence: success states are currently inline jade paragraphs in multiple pages, while loading/empty/error/fallback have shared components.  
   Fix: add `SuccessState` and align the shared state component surfaces.

5. **Chat entry is absent from the frontend.**  
   Evidence: backend `/api/ai/chat` exists, but no `/chat` frontend route or primary navigation entry exists.  
   Fix: add a lightweight `/chat` page that calls the backend through the typed API client; do not expose keys in frontend code.

## Medium Priority

- Dashboard and Reports need stronger visual hierarchy for summary, caveats, and next actions.
- Mobile navigation should be optimized for narrow screens with a stable scrollable primary nav and compact utility links.
- Empty states should point to the next useful workflow step instead of only explaining missing data.
- Report list should make generated assets and evidence boundaries scannable without repeating long explanatory copy.

## Low Priority

- Some seeded/demo company names include E2E or mojibake-looking strings in production data; this is data hygiene rather than layout breakage.
- Several state-signal keyword checks detect words like `失败` inside explanatory caveats, not necessarily live errors. Copy can be tightened later to reduce false alarm language.
- Future PDF export needs a single page-level capability notice once enabled, not per-card disabled controls.

## Top 5 Fixes Selected

1. Navigation clarity and responsive nav.
2. Homepage workflow rewrite and CTA priority.
3. Shared `SuccessState` plus aligned state components.
4. Lightweight `/chat` page and typed API client method.
5. Dashboard/Reports hierarchy and report-card action cleanup.

## Audit Limits

- This pass used DOM and viewport inspection rather than a full authenticated user-flow screenshot deck.
- Accessibility observations are limited to visible structure and navigation affordances; full keyboard and screen-reader testing remains a follow-up.
- Production data quality issues were observed but not treated as frontend code defects unless they affected layout or comprehension.
