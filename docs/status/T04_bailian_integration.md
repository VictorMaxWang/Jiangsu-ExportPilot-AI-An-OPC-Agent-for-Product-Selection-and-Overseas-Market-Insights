# T04 阿里云百炼统一调用服务

- 任务编号与名称：T04 阿里云百炼统一调用服务
- 负责线程：T04 阿里云百炼 qwen3.6-plus 接入开发 Agent
- 开始时间：2026-05-27T10:18:00+08:00
- 完成时间：2026-05-27T10:25:25+08:00

## 完成内容

- 在后端配置中新增百炼/DashScope 读取项：`DASHSCOPE_API_KEY` 优先，兼容 `BAILIAN_API_KEY`，并提供默认 base URL、模型、超时和重试配置。
- 新增 `backend/app/services/ai/`，封装 OpenAI-compatible Chat Completions 调用、JSON 输出模式、超时、重试和安全错误类型。
- 新增 AI prompt 模板，覆盖产品关键词、竞品摘要、国家市场解释、营销文案和报告段落。
- 新增 `POST /api/ai/chat`、`POST /api/ai/product-keywords`、`POST /api/ai/marketing-copy`、`POST /api/ai/report-section`。
- 新增结构化 JSON 解析器，支持标准 JSON、markdown code fence 和前后多余文本中的首个 JSON object。
- 新增后端测试，覆盖配置优先级、客户端重试、超时、JSON 解析、缺 Key、结构化接口和坏 JSON 错误。

## 修改路径

- `backend/app/core/config.py`
- `backend/app/api/ai.py`
- `backend/app/api/router.py`
- `backend/app/schemas/ai.py`
- `backend/app/schemas/__init__.py`
- `backend/app/services/__init__.py`
- `backend/app/services/ai/`
- `backend/tests/test_ai_integration.py`
- `docs/status/T04_bailian_integration.md`

## 验证结果

- `cd backend; py -3.11 -m pytest tests` 通过，结果 `25 passed`。
- `cd backend; python -m pytest tests` 未执行成功：本机默认 `python` 指向 MSYS Python，未安装 `pytest`。
- `cd backend; py -3.13 -m pytest tests` 未执行成功：该 Python 环境缺少 `SQLAlchemy`，不是当前项目已安装依赖环境。

## 安全说明

- 未把真实 API Key 写入代码、测试、`.env.example` 或状态文件。
- 百炼 Key 只由后端环境变量读取，前端不会接收、展示或代理传递 Key。
- 未设置 Key 时 AI 接口返回 `503` 和明确的 `BAILIAN_NOT_CONFIGURED` 错误。
- 错误响应不包含 `Authorization`、Bearer token、Key 明文、完整请求头或第三方原始响应体。
- 测试仅使用 fake key 和 `httpx.MockTransport`，不调用真实百炼网络。

## Blockers

- 无实现阻塞。

## Follow-up

- 若先前聊天中出现的 Key 是真实可用密钥，建议在阿里云控制台轮换后通过本地 `.env`、服务器环境变量或部署 Secret 配置新 Key。
- 后续 T14/T15/T17 可复用本 AI 服务，将 AI 输出按业务需要入库。
