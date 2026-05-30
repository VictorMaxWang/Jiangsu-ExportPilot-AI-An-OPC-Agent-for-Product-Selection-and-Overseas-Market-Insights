# Q19 国内商品链接导入线上验证

## 任务信息

- 任务编号：Q19
- 任务名称：Domestic URL Intake Live Validation
- 负责线程：Q19 domestic URL intake live validation agent
- 开始时间：2026-05-30 16:19:00 +08:00
- 结束时间：2026-05-30 16:24:00 +08:00

## 变更路径

- `docs/status/Q19_domestic_url_intake_live_validation.md`

## 执行边界

- 未读取、输出或提交任何 `.env`、Key、Cookie、Authorization、管理密码或上游原始错误正文。
- 未绕过登录、验证码、风控或平台短链限制。
- 未使用 Cookie、登录态、验证码服务、代理池或模拟登录。
- 因 Codex 内置浏览器不可用，未提交三条商品链接，未创建商品草稿，未确认入库。
- 按计划要求，未使用 `curl` 或其他浏览器替代内置浏览器执行 UI 链接导入验证。

## 浏览器可用性

Codex 内置浏览器连接失败。已按 Browser 插件工作流分别尝试 `browser` 与 `browser-use` 两个入口，均无法建立可信浏览器会话。结论：本线程无法打开 `https://opc.ankangyu.cn/products/import` 并执行 UI 提交。

## 安全预检结果

只执行了不含凭据的安全预检；未触发链接导入接口，未触发 AI smoke POST。

| Probe | 结果 | 备注 |
| --- | --- | --- |
| `GET https://opc.ankangyu.cn/health` | HTTP 200 | 返回 `status=ok`, `service=supinzhihang-backend` |
| `HEAD https://opc.ankangyu.cn/products/import` | HTTP 200 | Next.js 页面可达 |
| `GET https://opc.ankangyu.cn/api/ai/status` | HTTP 200 | `provider=bailian`, `model=qwen3.6-plus`, `configured=true`; status 字段为安全摘要 |

AI status 安全字段显示：文本模型 `qwen3.6-plus` 已配置；视觉模型 `qwen-vl-plus` 已配置。该接口本身未执行实时 smoke，因此本文件不把它作为 Qwen 文本生成成功证明。

## 本地解析器复核

该复核只用于判断线上验证风险，不代表线上结果。

| 链接 | 本地平台识别 | 本地解析状态 | 备注 |
| --- | --- | --- | --- |
| 淘宝短链 `https://e.tb.cn/h.Rg7IXlmjiRJ5ifv?tk=...` | `unknown` | `unsupported_domain` | 当前本地解析器不支持 `e.tb.cn` 短链域名 |
| 拼多多 `https://mobile.yangkeduo.com/goods2.html?ps=...` | `pinduoduo` | `missing_item_id` | 未从 `ps` 参数解析出商品 ID，预期应兜底为截图导入 |
| 京东短链 `https://3.cn/-2Q1WvH7?jkl=...` | `unknown` | `unsupported_domain` | 当前本地解析器不支持 `3.cn` 短链域名 |

## 三条链接线上验证结果

| 平台 | 链接 | UI 提交 | 结构化状态 | Qwen 是否生成草稿 | 是否确认入库 | `/products` 是否可见 | 结果说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 淘宝 | `https://e.tb.cn/h.Rg7IXlmjiRJ5ifv?tk=S71r5yDJd3y` | 未执行 | 未观测 | 未观测 | 否 | 未验证 | 浏览器不可用，未用其他方式替代 UI 提交；本地解析器存在短链 `unsupported_domain` 风险 |
| 拼多多 | `https://mobile.yangkeduo.com/goods2.html?ps=zheeHWNSNR` | 未执行 | 未观测 | 未观测 | 否 | 未验证 | 浏览器不可用，未用其他方式替代 UI 提交；本地解析器预期 `missing_item_id` 后应返回 `needs_screenshot` |
| 京东 | `https://3.cn/-2Q1WvH7?jkl=@X59VX7JUQ1@` | 未执行 | 未观测 | 未观测 | 否 | 未验证 | 浏览器不可用，未用其他方式替代 UI 提交；本地解析器存在短链 `unsupported_domain` 风险 |

## Fallback 提示验证

- 未验证。由于内置浏览器不可用，无法提交链接并观察前端是否展示：
  `该平台页面可能需要登录或动态渲染，请上传商品截图继续分析`
- 未发现 HTTP 500，因为没有触发三条链接导入请求。

## 测试与命令结果

- Browser 插件连接：失败，无法建立 Codex 内置浏览器会话。
- `GET /health`：HTTP 200。
- `HEAD /products/import`：HTTP 200。
- `GET /api/ai/status`：HTTP 200，仅记录安全摘要字段。
- 本地 `parse_domestic_product_url` 复核：淘宝短链 `unsupported_domain`，拼多多链接 `missing_item_id`，京东短链 `unsupported_domain`。

## Blockers 与 Follow-up

- Blocker：Codex 内置浏览器当前不可用，无法完成计划要求的线上 UI 验证、草稿确认入库和 `/products` 可见性检查。
- Follow-up：在内置浏览器可用的线程中重新打开 `https://opc.ankangyu.cn/products/import`，逐条提交三条链接，并记录 `status`、`ai_result_type`、`ai_fallback_used`、`model_used`、`error_code`、`draft_id`、`job_id` 和页面提示。
- Follow-up：如果淘宝 `e.tb.cn` 或京东 `3.cn` 短链在线上返回 4xx 而不是 `needs_screenshot` / `failed` 的结构化状态，应修复短链或 unsupported-domain 兜底，使其不产生 500 且能提示上传截图。
- Follow-up：如果任何链接返回 `draft_ready`，必须确认 `ai_result_type=real_qwen`、`model_used=qwen3.6-plus`，再确认入库并验证 `/products` 页面可见。

## Continuation Audit

- 2026-05-30 16:24:35 +08:00 继续复查：当前工作树除本文件外，另有未跟踪的 `docs/status/Q18_screenshot_intake_live_validation.md`，本线程未修改该文件。
- 重新检查 Browser 插件入口文件：`browser` 导出 `setupBrowserRuntime`，`browser-use` 导出 `setupAtlasRuntime`；两者均依赖当前会话可用的 Codex 原生浏览器连接。
- 再次通过工具发现确认：当前没有额外的 Browser 专用导航、截图或点击工具暴露，仍只能通过同一 Node/browser-client 通道访问内置浏览器。
- 阻塞条件未变化：当前会话缺少可用的内置浏览器原生连接，因此仍无法执行 `/products/import` UI 提交、草稿确认入库或 `/products` 可见性验证。
- 2026-05-30 16:26:42 +08:00 目标恢复为 active 后再次复查：`browser` 与 `browser-use` 两个 Browser 插件入口均返回同一连接错误，未打开 `/products/import`，未提交任何链接。
- 本次恢复是 blocked 后的第一轮复查；按目标规则暂不再次标记 blocked，等待后续轮次或外部浏览器连接恢复。
- 2026-05-30 16:29:39 +08:00 第二轮恢复复查：工作树状态未变化；再次尝试 `browser` 与 `browser-use` 两个 Browser 插件入口，仍均返回同一内置浏览器原生连接错误。
- 本次仍未打开 `/products/import`，未提交淘宝、拼多多或京东链接，未创建草稿，未确认入库。该轮为 blocked 后恢复审计的第二轮，暂不再次标记 blocked。
- 2026-05-30 16:30:58 +08:00 第三轮恢复复查：目标仍为 active，Q19 文件存在，工作树状态未出现新的相关变动。
- 再次尝试 `browser` 与 `browser-use` 两个 Browser 插件入口，仍均返回同一内置浏览器原生连接错误；未打开 `/products/import`，未提交任何链接。
- 该阻塞已在恢复后连续三轮复现，且没有可用的 Codex 内置浏览器替代入口；本轮按目标规则重新标记 goal 为 blocked。
