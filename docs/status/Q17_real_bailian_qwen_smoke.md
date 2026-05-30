# Q17 真实百炼 Qwen 调用验收与配置修复

## 任务信息

- 任务编号：Q17
- 任务名称：真实百炼 Qwen 调用验收与配置修复
- 负责人线程：Q17 真实百炼 Qwen 调用验收与配置修复 Agent
- 开始时间：2026-05-30 10:19:00 +08:00
- 完成时间：2026-05-30 11:01:46 +08:00

## 修改路径

- `backend/app/api/ai.py`
- `backend/app/schemas/ai.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/product_intake.py`
- `backend/app/services/ai/bailian_client.py`
- `backend/app/services/product_intake/screenshot_analyzer.py`
- `backend/app/services/product_intake/url_intake.py`
- `backend/tests/test_ai_integration.py`
- `backend/tests/test_product_intake_screenshot_api.py`
- `backend/tests/test_product_intake_url_api.py`
- `frontend/app/_lib/api-client.ts`
- `frontend/app/products/import/_components/ProductImportWorkspace.tsx`
- `frontend/tests/product-intake.spec.ts`
- `docs/status/Q17_real_bailian_qwen_smoke.md`

## 完成内容

- 新增 `GET /api/ai/status`、`POST /api/ai/smoke/text`、`POST /api/ai/smoke/vision`。
- smoke 响应统一返回 `provider`、`model`、`configured`、`success`、`fallback_used`、`sanitized_error`。
- text smoke 调用配置的 `qwen3.6-plus` 文本模型；vision smoke 在内存生成小 PNG 后调用环境配置的视觉模型。
- 视觉模型未启用或未配置时，vision smoke 和截图导入均明确返回失败/人工补全状态，不 mock 成真实分析成功。
- 截图和链接导入响应新增 `ai_result_type`、`ai_fallback_used`、`model_used`，URL 响应补充 `error_code`、`error_message`。
- 前端导入页显示“真实 Qwen 识别 / AI 回退草稿 / 需要人工处理”，并显示是否 AI 回退与模型名。

## 验证命令与结果

- `cd backend && py -3.11 -m pytest tests/test_ai_integration.py tests/test_product_intake_screenshot_api.py tests/test_product_intake_url_api.py -q`：通过，56 passed。
- `cd backend && py -3.11 -m pytest tests -q`：通过，270 passed。
- `cd frontend && npm run lint`：通过，无 ESLint warnings 或 errors。
- `cd frontend && npm run build`：通过，Next.js production build 成功。
- `cd frontend && npm run test:e2e`：通过，3 passed。
- `git diff --check`：通过，仅 Windows 工作区换行提示。

## Smoke 结果

### 本地后端进程

| Endpoint | HTTP | Provider | Model | Configured | Success | Fallback used | Sanitized error |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET /api/ai/status` | 200 | `bailian` | `qwen3.6-plus` | false | false | false | `BAILIAN_NOT_CONFIGURED` |
| status text | 200 | `bailian` | `qwen3.6-plus` | false | false | false | `BAILIAN_NOT_CONFIGURED` |
| status vision | 200 | `bailian` | none | false | false | false | `BAILIAN_VISION_DISABLED` |
| `POST /api/ai/smoke/text` | 200 | `bailian` | `qwen3.6-plus` | false | false | false | `BAILIAN_NOT_CONFIGURED` |
| `POST /api/ai/smoke/vision` | 200 | `bailian` | none | false | false | false | `BAILIAN_VISION_DISABLED` |

本地运行环境未配置后端模型凭据，未发生真实上游调用成功；失败原因已用脱敏错误码记录。

### 生产站点

| Probe | Result |
| --- | --- |
| `GET https://opc.ankangyu.cn/health` | HTTP 200 |
| `GET https://opc.ankangyu.cn/api/ai/status` | HTTP 404 |

生产站点当前尚未部署 Q17 新接口，因此未继续触发生产 text/vision smoke。待生产部署完成后，应重新调用三个 Q17 AI 接口并只记录安全字段。

## 安全结果

- 未读取、输出或提交任何 `.env` 文件内容。
- 未输出任何凭据值、请求头、Cookie、Authorization 内容或上游原始错误正文。
- Q17 真实 Bailian 调用凭据读取已收敛为后端进程环境变量 `DASHSCOPE_API_KEY`。
- smoke 测试只记录成功/失败、模型名、配置状态和脱敏错误码。
- 前端和测试只使用响应状态字段，不接收或展示第三方凭据。

## Blockers 与 Follow-up

- Blocker：当前生产站点仍返回 `/api/ai/status` 404，说明 Q17 代码尚未部署到生产站点；本线程没有可用的无凭据生产发布通道。
- Follow-up：生产部署后复测 `GET /api/ai/status`、`POST /api/ai/smoke/text`、`POST /api/ai/smoke/vision`。
- Follow-up：如需 vision smoke 成功，生产后端必须启用视觉功能并配置可用的视觉模型。

## Continuation Audit

- 2026-05-30 11:09:20 +08:00 复查当前工作树：`cd frontend && npm run lint` 通过；`cd frontend && npm run build` 通过。
- 生产复查：`GET https://opc.ankangyu.cn/health` 仍为 HTTP 200；`GET https://opc.ankangyu.cn/api/ai/status` 仍为 HTTP 404。
- 结论：本地实现和验证完成，生产站点尚未部署 Q17 新接口，生产 smoke 仍需部署后复测。
- 2026-05-30 11:11:17 +08:00 复查部署路径：`.github/workflows/ci.yml` 只有 CI 检查，没有生产发布；`scripts/deploy_prod.sh` 依赖服务器本地 `.env` 和 Docker Compose，本线程不能读取 `.env` 或代替服务器执行部署。
- 第三次生产复查：`GET https://opc.ankangyu.cn/health` 为 HTTP 200；`GET https://opc.ankangyu.cn/api/ai/status` 为 HTTP 404。
- 当前阻塞条件：生产部署与部署后 smoke 复测需要服务器部署权限或控制线程执行生产发布。
- 2026-05-30 11:14:08 +08:00 再次复查生产：`GET https://opc.ankangyu.cn/health` 为 HTTP 200；`GET https://opc.ankangyu.cn/api/ai/status` 仍为 HTTP 404，阻塞条件未变化。
- 2026-05-30 11:15:22 +08:00 再次复查生产：`GET https://opc.ankangyu.cn/health` 为 HTTP 200；`GET https://opc.ankangyu.cn/api/ai/status` 仍为 HTTP 404，未触发生产 smoke。
- 2026-05-30 11:16:48 +08:00 再次复查生产：`GET https://opc.ankangyu.cn/health` 为 HTTP 200；`GET https://opc.ankangyu.cn/api/ai/status` 仍为 HTTP 404，未触发生产 smoke。
- 2026-05-30 11:18:50 +08:00 再次复查生产：`GET https://opc.ankangyu.cn/health` 为 HTTP 200；`GET https://opc.ankangyu.cn/api/ai/status` 仍为 HTTP 404，未触发生产 smoke。
- 2026-05-30 11:23:31 +08:00 安全收敛后复跑：Bailian 真实调用凭据读取限定为 `DASHSCOPE_API_KEY`；`cd backend && py -3.11 -m pytest tests -q` 通过，270 passed；`cd frontend && npm run lint` 通过；`cd frontend && npm run build` 通过。
