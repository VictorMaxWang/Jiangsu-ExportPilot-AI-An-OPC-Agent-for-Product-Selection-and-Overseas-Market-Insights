# R13 数据源能力状态页

- 任务编号与名称：R13 数据源能力状态页
- 负责线程：R13 数据源能力状态页 Agent
- 开始时间：2026-05-28T09:00:00+08:00
- 完成时间：2026-05-28T09:34:20+08:00

## 完成内容

- 新增 `GET /api/admin/providers/status`，返回 10 个 provider 的安全状态枚举、优先级、默认启用状态、fallback 文件和说明。
- 新增 `POST /api/admin/providers/test/{provider}`，支持 P0/P1 provider 的安全连通性测试，eBay/Rakuten/Reddit 固定返回待注册状态且不尝试真实调用。
- 新增后端 provider status schema 与 service，统一处理：
  - Bailian 缺配置返回 `pending`，配置后执行短 prompt 测试。
  - World Bank、GDELT、YouTube、Etsy、UN Comtrade 复用现有后端 provider client。
  - CSV fallback 校验 `data/seed/*.csv` 核心文件可读且非空。
  - 所有异常映射为固定安全消息和内部错误码，不返回上游原始错误。
- `/admin/api-keys` 改为“数据源能力状态”页面，从后端读取真实状态并支持逐行测试。
- `/admin/data-sources` 复用同一状态视图，避免继续展示静态配置判断。
- 扩展前端 typed API client 与 provider badge 状态枚举。

## 修改路径

- `backend/app/api/admin/__init__.py`
- `backend/app/api/admin/providers.py`
- `backend/app/api/router.py`
- `backend/app/core/config.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/provider_status.py`
- `backend/app/services/provider_status.py`
- `backend/tests/test_provider_status_api.py`
- `frontend/app/_components/ProviderStatusBadge.tsx`
- `frontend/app/_lib/api-client.ts`
- `frontend/app/_lib/navigation.ts`
- `frontend/app/admin/_components/ProviderStatusDashboard.tsx`
- `frontend/app/admin/api-keys/page.tsx`
- `frontend/app/admin/data-sources/page.tsx`
- `docs/status/R13_provider_status_page.md`

## 验证结果

- `py -3.11 -m pytest backend\tests\test_provider_status_api.py -q`
  - 结果：`9 passed`
- `cd backend; py -3.11 -m pytest tests -q`
  - 结果：`108 passed`
- `cd backend; py -3.11 -m compileall app`
  - 结果：通过
- `cd frontend; node .\node_modules\typescript\bin\tsc --noEmit`
  - 结果：通过
- `cd frontend; node .\node_modules\eslint\bin\eslint.js app --ext .ts,.tsx`
  - 结果：通过
- `cd frontend; npm run build`
  - 结果：304 秒超时，未返回编译错误文本；已停止本次 build 进程。
- 临时启动 `uvicorn` 于 `127.0.0.1:8013`，验证 `/api/admin/providers/status` 返回 10 个 provider；验证后已停止临时进程。

## 受限验证

- `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8013 npm run dev -- --hostname 127.0.0.1 --port 3333` 长时间停留在 Next `Starting...`，`/admin/api-keys` 请求超时；已停止临时前端进程。
- Browser 插件连接失败，提示 `browser-client is not trusted`，因此未完成 in-app browser 截图和交互验收。
- 现有本机 `127.0.0.1:8000` 被非项目进程占用，本次后端临时验证改用 `8013`。

## 安全记录

- 未写入真实 API 凭据、cookie、数据库密码或云服务凭据。
- 后端状态接口不返回凭据值、片段、长度、哈希、掩码、请求头、完整上游 URL、查询参数或上游原始错误。
- 前端页面仅展示 provider 状态、优先级、默认启用、fallback 文件、测试按钮和最近测试结果。
- 新增测试使用 fake env 值断言响应中不包含敏感标记或假凭据值。
- eBay、Rakuten、Reddit 当前仅返回待注册状态，即使环境变量存在也不标记为真实可用。

## Subagent 审查记录

- `backend-status-agent`：建议新增独立 admin provider status 层，不改现有 `/api/data/*` 行为。
- `frontend-status-agent`：建议用 typed API client 和客户端状态表替换静态 admin catalog。
- `security-agent`：要求错误处理不得回传原始异常、上游 URL、headers 或凭据派生信息。
- `provider-test-agent`：确认各 provider 的 success/fallback/pending/unavailable 映射。
- `reviewer-agent`：指出 R13 需要补齐状态文件，并记录 build/dev 运行限制。

## Follow-up Notes

- Next 本地 build/dev 卡在启动阶段的问题延续自 R12 记录，建议后续单独排查本机 Next 运行环境或 `.next` 状态。
- 如后续真实接入 eBay/Rakuten/Reddit，需要新增后端 provider client、fallback 数据和单独安全测试后再改变 pending 状态。
