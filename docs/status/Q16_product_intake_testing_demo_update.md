# Q16 智能商品导入测试、部署和演示材料更新

## 任务信息

- 任务编号：Q16
- 任务名称：智能商品导入测试、部署和演示材料更新
- 负责人线程：Q16 智能商品导入测试、部署和演示材料更新 Agent
- 开始时间：2026-05-29 21:18:00 +08:00
- 完成时间：2026-05-29 21:44:22 +08:00

## 修改路径

- `.gitignore`
- `backend/Dockerfile`
- `backend/tests/test_domestic_page_fetcher.py`
- `backend/tests/test_domestic_url_parser.py`
- `backend/tests/test_product_intake_screenshot_api.py`
- `backend/tests/test_product_intake_url_api.py`
- `backend/tests/test_product_intake_draft_api.py`
- `backend/tests/test_intake_analysis_report_flow.py`
- `backend/tests/test_report_generation.py`
- `docker-compose.prod.yml`
- `docs/DEPLOYMENT_TENCENT_CLOUD.md`
- `docs/competition/DEMO_SCRIPT_5MIN.md`
- `docs/competition/JUDGES_QA.md`
- `docs/competition/PPT_OUTLINE_15P.md`
- `docs/demo/README.md`
- `docs/status/Q16_product_intake_testing_demo_update.md`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/playwright.config.ts`
- `frontend/tests/product-intake.spec.ts`

## 完成内容

- 扩展后端截图导入测试，覆盖 JPEG/WebP、MIME 与真实内容不匹配、空文件、企业不存在、视觉识别关闭或未配置模型、敏感证据脱敏和安全响应。
- 新增 URL fetcher SSRF 测试，覆盖私网 DNS 解析、重定向到私网、重定向 userinfo/异常端口、重定向上限和请求头不携带 Cookie/Authorization。
- 扩展 URL intake 测试，覆盖淘宝/天猫/拼多多规范化、`ENABLE_DOMESTIC_URL_FETCH=false` 的 `needs_screenshot`、缺少商品 ID、空页面回退、AI JSON/Schema/低置信度/未识别/超时失败和敏感查询参数不回显。
- 扩展草稿和分析闭环测试，覆盖缺失 job/draft 404、确认前中文名校验回滚、截图来源产品确认后进入 analysis/dashboard/report，并验证来源说明和国内价格边界。
- 新增 Playwright E2E，使用 mock API 覆盖 `/products/import` 访问、截图文件选择、链接输入、`needs_screenshot` 提示、草稿保存/确认和产品列表展示。
- 更新生产 Docker 配置：后端传递智能导入环境变量，`product_uploads` named volume 挂载到 `/app/storage/product-intake`，后端镜像创建并授权上传目录。
- 更新腾讯云部署文档，补充上传目录持久化、GitHub 排除、图片大小限制、链接解析失败截图兜底、视觉模型开关和生产安全默认值。
- 创建比赛演示材料：5 分钟演示脚本、评委问答、15 页 PPT 大纲；`docs/demo/README.md` 作为指向入口。

## 验证命令与结果

- `cd backend && py -3.11 -m pytest tests/test_product_intake_screenshot_api.py tests/test_domestic_page_fetcher.py tests/test_domestic_url_parser.py tests/test_product_intake_url_api.py tests/test_product_intake_draft_api.py tests/test_intake_analysis_report_flow.py tests/test_report_generation.py -q`：通过，83 passed。
- `cd backend && py -3.11 -m pytest tests -q`：通过，266 passed in 19.95s。
- `cd frontend && npm run lint`：通过，No ESLint warnings or errors。
- `cd frontend && npm run build`：通过，Next.js production build 成功，包含 `/products/import`。
- `cd frontend && npm run test:e2e`：通过，3 passed in 27.3s。
- `cd frontend && npx playwright install chromium`：未完成，300s 超时；本机已有系统 Chrome，Playwright 配置使用 Chrome channel 完成 E2E。
- `docker compose --env-file .env.example -f docker-compose.prod.yml config --quiet`：未运行成功，本机未安装 Docker CLI，提示 `docker` command not found。

## 环境变量影响

未新增变量名；本次在生产 Compose 和部署文档中补充已存在变量的生产传递与说明：

```text
BAILIAN_VISION_ENABLED
BAILIAN_VISION_MODEL
PRODUCT_UPLOAD_DIR
MAX_PRODUCT_IMAGE_SIZE_MB
ENABLE_DOMESTIC_URL_FETCH
```

## 安全与合规结果

- 未写入真实 API Key、Token、Cookie、Authorization 头、数据库密码或第三方凭据。
- 上传截图目录继续通过 `storage/` 和 Playwright 产物忽略规则避免进入 Git。
- 比赛材料明确不做批量采集、登录绕过、验证码绕过、代理池、模拟登录或平台官方验证表述。
- 国内商品截图/链接价格继续只作为参考信息，不作为海外售价、成交价、采购成本或利润依据。
- 链接解析失败、关闭或受限时统一引导上传截图，保持 `ENABLE_DOMESTIC_URL_FETCH=false` 为生产安全默认值。

## Blockers 与 Follow-up

- Blocker：本机未安装 Docker CLI，无法本地验证生产 Compose config；需在有 Docker 的部署机或 CI 中执行同等命令。
- Follow-up：`npx playwright install chromium` 在本机超时，当前 E2E 使用系统 Chrome channel；CI 若无 Chrome，应先安装 Playwright Chromium 或调整运行环境。
- Follow-up：`npm install --save-dev @playwright/test` 输出 5 个 npm audit vulnerabilities，延续既有依赖审计策略，不在 Q16 范围内强制升级。
