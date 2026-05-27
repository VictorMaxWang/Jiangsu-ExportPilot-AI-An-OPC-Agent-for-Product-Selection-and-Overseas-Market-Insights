# Jiangsu ExportPilot Agent Guide

This repository is the competition demo project **SuPin ZhiHang / Jiangsu ExportPilot** for the Jiangsu university "Silk Road E-commerce" innovation challenge, OPC intelligent agent application track.

All future Codex threads must follow this file before making changes.

## Project Mission

Build an AI product selection and overseas market insight platform for Jiangsu manufacturing companies. The system helps users enter product information, import sample CSV data, connect public data sources, call Alibaba Cloud Bailian `qwen3.6-plus`, score market opportunities, generate marketing copy, visualize insights, and export overseas expansion reports.

## Tech Stack

- Frontend: Next.js, TypeScript, Tailwind CSS, ECharts
- Backend: FastAPI, Python, Pydantic, SQLAlchemy
- Database: PostgreSQL
- AI: Alibaba Cloud Bailian `qwen3.6-plus`
- Deployment: Docker Compose, Tencent Cloud CVM, Nginx
- Data sources: World Bank, GDELT, eBay Browse API, UN Comtrade, Rakuten Ichiba, YouTube Data API, Etsy Open API, Reddit API, CSV fallback

## Expected Directory Structure

```text
.
├── AGENTS.md
├── agent.md
├── docs/
│   ├── API_SOURCES.md
│   ├── ARCHITECTURE.md
│   ├── PROJECT_BRIEF.md
│   ├── SECURITY.md
│   ├── TASK_BOARD.md
│   └── status/
├── frontend/
├── backend/
├── data/
│   ├── samples/
│   └── fallback/
├── deploy/
├── scripts/
└── tests/
```

Do not create unrelated top-level directories without updating the architecture and task board documents.

## Coordination Rules

- `agent.md` and `docs/TASK_BOARD.md` are master control documents. Avoid editing them from parallel task threads unless you are the control thread.
- Each implementation task must write a separate status file under `docs/status/`, for example `docs/status/T01_project_scaffold.md`.
- A task status file should include: task id, owner thread, start time, end time, changed paths, test results, blockers, and follow-up notes.
- Parallel tasks must not edit the same source files unless the control thread explicitly coordinates the dependency.
- Prefer small, reviewable changes. Keep each task aligned with its assigned Txx scope.

## Naming Rules

- Task ids: `T00` through `T22`.
- Backend Python modules: `snake_case`.
- Frontend components: `PascalCase`.
- Frontend hooks: `useCamelCase`.
- API route paths: kebab-case or stable REST-style nouns, for example `/api/market-insights`.
- Database tables: `snake_case` plural nouns, for example `market_scores`.
- Environment variables: `UPPER_SNAKE_CASE`.
- Status files: `Txx_short_description.md`, for example `T13_bailian_client.md`.

## Security Requirements

- Never write real API keys, tokens, credentials, cookies, or secrets into the repository.
- All API keys must be read only by the backend from environment variables.
- The frontend must never receive or expose third-party API keys.
- Never print secrets in logs, exceptions, debug panels, screenshots, or generated reports.
- Do not commit `.env`.
- Maintain `.env.example` with placeholder names only.
- Admin/config screens may show only "configured" or "not configured"; they must not show plaintext secret values.
- If a key is accidentally exposed, stop and document the risk in `docs/status/` before continuing.

## Environment Variable Policy

Use descriptive backend-only variable names. Expected examples:

```text
DATABASE_URL=
BAILIAN_API_KEY=
BAILIAN_MODEL=qwen3.6-plus
EBAY_CLIENT_ID=
EBAY_CLIENT_SECRET=
UN_COMTRADE_API_KEY=
RAKUTEN_APP_ID=
YOUTUBE_API_KEY=
ETSY_API_KEY=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
```

Values must appear only in local `.env` files, deployment secret stores, or server environment configuration.

## Code Style

- TypeScript: strict mode, explicit domain types, no `any` unless justified with a short comment.
- React: prefer server components where practical, isolate interactive UI in client components, keep data fetching behind typed API clients.
- Styling: Tailwind CSS with reusable layout and UI primitives; avoid one-off inline styles for standard UI.
- Charts: use ECharts through a small wrapper component so chart option construction stays testable.
- Python: type hints, Pydantic schemas for request/response models, SQLAlchemy models for persistence.
- FastAPI: keep routers, services, clients, schemas, and models separated.
- External APIs: wrap each provider behind a backend client with timeout, retry policy, normalized output, and CSV fallback where available.
- AI calls: centralize prompt templates and response parsing. Never call Bailian directly from frontend code.

## Testing and Validation

- Backend: add focused tests for services, API clients, scoring logic, and report generation.
- Frontend: test core user flows and key components when behavior is non-trivial.
- Integration: include sample CSV import, fallback data path, AI mock path, and dashboard rendering path.
- Before marking a task done, run the smallest relevant checks and record results in that task's `docs/status/Txx_*.md`.

## Git and Commit Requirements

- Do not commit generated caches, local virtual environments, `.env`, build artifacts, or private data.
- Keep commits scoped to one task or one coherent change.
- Commit messages should start with the task id when applicable, for example `T04 add FastAPI health routes`.
- Do not rewrite or revert another thread's work unless explicitly instructed by the control thread.

## Documentation Requirements

- Public project behavior belongs in `docs/`.
- Task execution notes belong in `docs/status/`.
- When changing architecture, security policy, data source behavior, or task scope, update the relevant document in the same change.
- Keep Chinese user-facing project control docs readable for competition reviewers.
