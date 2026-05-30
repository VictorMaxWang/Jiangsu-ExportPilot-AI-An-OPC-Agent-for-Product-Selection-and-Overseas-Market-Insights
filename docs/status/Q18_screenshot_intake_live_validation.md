# Q18 截图导入真实 Qwen 视觉链路线上验证

## 任务信息

- 任务编号：Q18
- 任务名称：截图导入真实 Qwen 视觉链路线上验证
- 负责线程：Codex Q18 screenshot intake live validation
- 开始时间：2026-05-30 16:18:00 +08:00
- 结束时间：2026-05-30 16:22:11 +08:00

## 变更路径

- `docs/status/Q18_screenshot_intake_live_validation.md`

未修改后端或前端源码。

## 线上验证目标

- 目标页面：`https://opc.ankangyu.cn/products/import`
- 目标企业：`#2 E2E Smoke Test Nantong Home Textile`
- 预期链路：截图导入优先走真实 Qwen 视觉分析，返回 `ai_result_type=real_qwen` 且 `ai_fallback_used=false`
- 预期入库：确认草稿后在 `/products?company_id=2` 可见新增产品

## 执行结果

本次线上截图导入验证未能继续执行。

- Codex Browser 插件在打开生产导入页前失败，表现为本地浏览器桥接未被信任。
- 按计划约束，未切换到其他浏览器、HTTP 直调或脚本上传方式继续验证，避免绕过“必须使用 Codex 内置浏览器”的验证前提。
- 未采集淘宝、拼多多或京东截图。
- 未向生产 `/api/product-intake/screenshot` 上传文件。
- 未创建 `product_draft`、`ProductImportJob` 或 `ProductImportAsset`。
- 未确认入库产品。
- 未触发或验证 `/products?company_id=2` 新增产品展示。

## 截图与识别记录

| 序号 | 截图来源 | 平台 | 上传结果 | `ai_result_type` | `ai_fallback_used` | 草稿 ID | 产品 ID | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 未执行 | 未执行 | 未上传 | 未返回 | 未返回 | 无 | 无 | Browser 插件阻塞 |
| 2 | 未执行 | 未执行 | 未上传 | 未返回 | 未返回 | 无 | 无 | Browser 插件阻塞 |

## 草稿字段验证

未生成草稿，因此以下字段均未能在线上响应中验证：

- `product_name_cn`
- `product_name_en`
- `category`
- `price_cny`
- `material`
- `specification`
- `selling_points`
- `target_users`
- `cross_border_keywords_en`
- `confidence_score`
- `evidence`

## 问题与修复

- Blocker：Codex Browser 插件无法建立受信任的内置浏览器连接，导致无法按计划打开 `https://opc.ankangyu.cn/products/import`。
- 本次未发现或修改应用源码问题。
- 未进行生产截图上传，因此无法判断当前生产截图导入是否返回 `real_qwen` 或是否存在 500。

## 验证命令与结果

- `py -3.11 -m pytest tests/test_ai_integration.py tests/test_product_intake_screenshot_api.py tests/test_product_intake_draft_api.py -q`：通过，56 passed。
- `npm run lint`：通过，无 ESLint warnings 或 errors。
- `npm run build`：通过，Next.js production build 成功。

## 安全记录

- 未读取、输出或提交 `.env`、API Key、Cookie、Authorization header、管理密码或平台登录态。
- 未绕过登录、验证码或风控。
- 未向第三方平台或生产导入接口提交敏感数据。

## Follow-up

- 修复或重新信任 Codex Browser 插件的本地浏览器桥接后，重新执行 Q18 线上验证。
- 重新验证时继续使用企业 `#2`，并记录每张截图的来源、识别字段、`ai_result_type`、`ai_fallback_used`、草稿 ID、产品 ID 和 `/products?company_id=2` 展示结果。

## Continuation Audit

- 2026-05-30 16:24:38 +08:00：按目标继续尝试 Codex Browser 内置浏览器。
- `browser-use/0.1.0-alpha2` 入口仍在打开生产导入页前失败，错误类型仍为本地浏览器桥接未被信任。
- `browser/0.1.0-alpha2` 备用入口同样在打开生产导入页前失败，错误类型相同。
- 按既定约束，未改用其他浏览器、HTTP 直调或脚本上传方式继续验证。
- 当前仍未上传截图、未生成草稿、未确认入库、未验证 `/products?company_id=2` 新增产品展示。
- 2026-05-30 16:26:53 +08:00：恢复目标后重新尝试 `browser-use/0.1.0-alpha2` 内置浏览器入口，仍在打开页面前失败，错误类型仍为本地浏览器桥接未被信任。
- 生产 `POST /api/ai/smoke/text`：`success=true`，`model=qwen3.6-plus`，`fallback_used=false`。
- 生产 `POST /api/ai/smoke/vision`：`success=true`，`model=qwen-vl-plus`，`fallback_used=false`。
- 生产 `GET /api/products?company_id=2`：当前仍为 3 条既有 E2E Smoke Test 产品；本轮没有新增 Q18 截图导入产品。
- 2026-05-30 16:29:33 +08:00：再次恢复目标后重试 `browser-use/0.1.0-alpha2` 内置浏览器入口，仍在打开生产导入页前失败。
- 本轮只读检查 Browser 插件本地脚本，失败发生在浏览器后端发现前：`import.meta.__codexNativePipe` 未注入，客户端返回“browser-client is not trusted”。
- 本轮安全检查的请求元数据仅包含 thread/session/turn 信息，未看到可供 Browser 客户端使用的浏览器能力字段；没有读取或输出任何凭据、Cookie、登录态或 `.env`。
- 结论保持不变：当前环境的 Codex Browser 本地桥接不可用，无法按“必须使用 Codex 内置浏览器”的约束完成截图 UI 上传验证。
- 2026-05-30 16:31:24 +08:00：再次恢复目标后重试 `browser-use/0.1.0-alpha2` 内置浏览器入口，仍在打开生产导入页前失败，错误类型相同。
- 本轮只读检查 `C:\Users\12804\.codex\browser\config.toml`，仅包含 Browser approval 默认值，没有可修复的本地桥接信任开关。
- 本轮只读检查 Codex 日志目录，最近可读日志为旧日志，未提供当前线程可恢复的 Browser 后端信息。
- 生产 `POST /api/ai/smoke/text` 仍为 `success=true`，`model=qwen3.6-plus`，`fallback_used=false`。
- 生产 `POST /api/ai/smoke/vision` 仍为 `success=true`，`model=qwen-vl-plus`，`fallback_used=false`。
- 当前阻塞条件仍为 Codex Browser 本地原生桥接未注入；没有执行截图上传、草稿确认或入库验证。
