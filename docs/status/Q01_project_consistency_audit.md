# Q01 总控状态同步与项目一致性审计

- 任务编号与名称：Q01 总控状态同步与项目一致性审计
- 负责线程：Q01 总控状态同步与项目一致性审计 Agent
- 开始时间：2026-05-28T19:05:00+08:00
- 完成时间：2026-05-28T20:01:32+08:00
- 状态：done

## 审计范围

- 已阅读：`AGENTS.md`、`agent.md`、`docs/TASK_BOARD.md`、`docs/API_SOURCES.md`、`docs/API_CAPABILITY_MATRIX.md`、`docs/ARCHITECTURE.md`、`docs/PROJECT_BRIEF.md`、`docs/SECURITY.md`、`docs/status/` 下 Txx/Rxx 状态文件、`README.md`、`backend/app/api/router.py`、`frontend/app/_lib/api-client.ts`。
- 未读取、未复制、未输出：`cross_border_api_keys_and_docs.txt`、`.env`、`.env.local`、`secrets/` 下任何内容。

## 发现的文档不一致

- `docs/TASK_BOARD.md` 原先将 `R06-R21` 显示为 `not_started`，但 `docs/status/` 下已存在对应完成状态文件。
- `docs/TASK_BOARD.md` 原先的 `R06-R21` 名称与实际状态文件发生编号漂移。
- `agent.md` 原先仍写当前阶段仅 `T00-T04` 和 `R05` 完成，未反映 `R06-R21` 已完成。
- `docs/API_SOURCES.md` 和 `docs/API_CAPABILITY_MATRIX.md` 原先将 YouTube/Etsy 的 Key 可用性写成静态事实，未体现“由后端环境和状态接口判断”。
- World Bank/GDELT/P2 provider 的 fallback 描述曾指向 `data/fallback/*`，但当前实际数据集中在 `data/seed/*`。
- `README.md` 原先仍写百炼配置入口属于后续任务，实际 T04 已完成后端统一配置读取。
- `docs/ARCHITECTURE.md` 原先仍写样本在 `data/samples/`、fallback 在 `data/fallback/`，与当前 `data/seed/` 事实不一致。
- `AGENTS.md` 原先把 eBay/Rakuten/Reddit 与当前 runtime 数据源并列，容易误读为已完成 provider。
- `AGENTS.md` 和 `README.md` 原先混有 `YOUTUBE_API_KEY`、`ETSY_API_KEY` 等非当前后端 runtime 变量名。
- `docs/PROJECT_BRIEF.md` 原先把 eBay/Rakuten/Reddit 写成外部数据源接入项，并将 PDF 报告表述为当前核心能力；实际 eBay/Rakuten/Reddit 是 P2 future provider，PDF 导出是 v1 后续增强。

## 发现的接口不一致

- 前端 `frontend/app/_lib/api-client.ts` 当前调用路径均能在 FastAPI 路由中找到对应定义，未发现前端调用不存在后端实现的路径。
- 产品导入同时存在 `/api/products/import` 和 `/api/import/products`。当前前端使用 `/api/products/import`；`/api/import/products` 可作为兼容/通用导入入口，后续可统一 canonical path。
- 健康检查当前是 `/health`，不是 `/api/health`。当前前端未调用健康检查；部署阶段需要确认探针路径或补别名。
- 后端还有 `/api/ai/*`、`/api/data/*`、`/api/data-sources/*`、`/api/markets/*`、`/api/scoring/*` 和 `/api/trends/*` 等底层能力接口，当前主前端 client 未直接封装，这属于入口分层，不是路径冲突。
- `/api/reports/{id}/download?format=pdf` 暴露 PDF 参数但当前 PDF 未实现，应继续记录为 v1 后续增强，避免形成交付承诺。

## 发现的命名不一致

- 旧任务板中的 R 编号与实际 R 状态文件名称不一致，已在任务板中按实际状态文件重排。
- 旧规则只提 `Txx` 状态文件，当前项目已进入 `Rxx` 和 `Qxx` 阶段，已同步总控规则。
- 当前实际 fallback 目录是 `data/seed/`，不是旧文档中的 `data/fallback/`。
- `/api/import` 使用单数资源组，而多数业务 API 使用复数资源组；当前保留兼容，后续可统一命名。
- `/api/ai/*` 与 `/api/marketing/generate`、`/api/products/{id}/generate-keywords` 有底层/业务入口重叠；当前主流程以前端业务入口为准。

## 修复内容

- 重写 `agent.md`，同步当前阶段、真实数据源、fallback 策略和 `Q01-Q08` 后续任务。
- 重写 `docs/TASK_BOARD.md`，将 `T00-T04`、`R05-R21` 和 `Q01` 标记为 done，并列出 `Q02-Q08`。
- 重写 `docs/API_SOURCES.md` 和 `docs/API_CAPABILITY_MATRIX.md`，移除静态 Key 可用性断言，改为环境相关/状态接口判断。
- 更新 `README.md` 的 Bailian 配置说明、当前后端 runtime 环境变量和状态文件命名说明。
- 更新 `AGENTS.md` 的 `data/seed/` 事实、任务编号规则、状态文件规则、当前/P2 数据源边界和环境变量示例。
- 更新 `docs/ARCHITECTURE.md` 的 CSV fallback 数据路径说明，并区分当前 runtime 数据源与 P2 future provider。
- 更新 `docs/PROJECT_BRIEF.md` 的数据源边界和报告能力边界，明确 PDF 导出不是当前 MVP 验收条件。
- 新增 `docs/PROJECT_STATUS_SUMMARY.md`。
- 新增本状态文件。

## 修改路径

- `AGENTS.md`
- `README.md`
- `agent.md`
- `docs/TASK_BOARD.md`
- `docs/API_SOURCES.md`
- `docs/API_CAPABILITY_MATRIX.md`
- `docs/ARCHITECTURE.md`
- `docs/PROJECT_BRIEF.md`
- `docs/PROJECT_STATUS_SUMMARY.md`
- `docs/status/Q01_project_consistency_audit.md`

## 验证命令与结果

```powershell
cd backend
py -3.11 -m pytest tests -q
```

结果：通过，`157 passed in 22.54s`。

```powershell
cd frontend
npm run lint
```

结果：通过，`No ESLint warnings or errors`。

```powershell
cd frontend
npm run build
```

结果：通过，Next.js production build 成功，生成 12 个 app routes。

文档验收：

```powershell
Test-Path docs\PROJECT_STATUS_SUMMARY.md
Select-String -Path docs\TASK_BOARD.md -Pattern 'R06.*not_started|R21.*not_started' -Encoding UTF8
Select-String -Path AGENTS.md,agent.md,README.md,docs\*.md -Pattern 'YouTube 未获得 Key|Etsy 不可用|R06 not_started|R06.*not_started|R21.*not_started|key_available \| yes|data/fallback|YOUTUBE_API_KEY|ETSY_API_KEY' -Encoding UTF8
```

结果：`docs/PROJECT_STATUS_SUMMARY.md` 存在；当前主控/公开文档中旧 `R06/R21 not_started`、指定过时表述、旧 YouTube/Etsy 变量名和 `data/fallback` 当前运行路径未检出。`data/fallback` 仅保留在历史状态文件或 Q01 审计对旧漂移的说明中，不作为当前运行路径。

安全验收：

```powershell
git check-ignore -v cross_border_api_keys_and_docs.txt .env .env.local secrets/foo.txt
git ls-files --stage -- cross_border_api_keys_and_docs.txt .env .env.* secrets/*
```

结果：敏感本地路径被 `.gitignore` 规则忽略；`git ls-files` 仅显示已跟踪的 `.env.example` 占位文件。

## 安全记录

- 未引入新的代码环境变量读取项；仅同步公开文档中的变量名到当前后端配置事实。
- 未读取、复制或输出真实 API Key、Secret、Token、Cookie、认证头或完整敏感连接串。
- 仅计划使用 `git check-ignore` 和 `git ls-files` 核对敏感文件忽略/跟踪状态，不读取文件内容。

## Blockers

- 无实现阻塞。

## Follow-up

- Q02：真实 API 冒烟测试与缓存绕过。
- Q03：Admin 保护与密钥扫描。
- Q04：主流程体验修复。
- Q06：确认 `/health` 与可能的 `/api/health` 部署探针策略。
- 后续可统一产品导入 canonical path。
- 后续可统一 `/api/ai/*` 底层接口与业务入口的 API 文档边界。
