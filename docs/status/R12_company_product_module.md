# R12 企业与产品管理模块

- 任务编号与名称：R12 企业与产品管理模块
- 负责线程：R12 企业与产品管理模块 Agent
- 开始时间：2026-05-28T08:00:00+08:00
- 完成时间：2026-05-28T08:42:40+08:00

## 完成内容

- 补齐企业 CRUD：`GET/POST/GET{id}/PUT/DELETE /api/companies`。
- 补齐产品 CRUD：`GET/POST/GET{id}/PUT/DELETE /api/products`。
- 新增 `POST /api/products/import`，支持：
  - JSON 导入 T03 `data/seed/product_catalog.csv`。
  - multipart 上传 CSV，并复用同一套产品 CSV 校验与导入逻辑。
- 新增 `POST /api/products/{id}/generate-keywords`：
  - 复用 T04 百炼 `qwen3.6-plus` 产品关键词生成逻辑。
  - 默认更新 `product_name_en`。
  - 将 `keywords_en`、`keywords_jp` 保存到 `product_keywords`，来源标记为 `bailian`，语言为 `en`/`ja`，重复生成不会重复写入同产品同语言同关键词。
- 新增前端 typed API client，DTO 保持后端 `snake_case`。
- `/companies` 改为真实企业管理页，支持列表、新增、编辑、删除、详情。
- `/products` 改为真实产品管理页，支持列表、新增、编辑、删除、样本 CSV 导入、上传 CSV 导入、关键词生成结果展示。
- 后端补齐 CORS 配置，默认允许 `http://localhost:3000`，支持 `CORS_ORIGINS` 逗号分隔配置。

## 修改路径

- `backend/app/api/ai.py`
- `backend/app/api/companies.py`
- `backend/app/api/products.py`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/products.py`
- `backend/app/services/ai/__init__.py`
- `backend/app/services/ai/product_keywords.py`
- `backend/app/services/product_service.py`
- `backend/requirements.txt`
- `backend/tests/test_database_api.py`
- `backend/tests/test_import_api.py`
- `backend/tests/test_product_keyword_api.py`
- `frontend/app/_lib/api-client.ts`
- `frontend/app/companies/page.tsx`
- `frontend/app/companies/_components/CompaniesWorkspace.tsx`
- `frontend/app/products/page.tsx`
- `frontend/app/products/_components/ProductsWorkspace.tsx`
- `docs/status/R12_company_product_module.md`

## 验证结果

- `cd backend; py -3.11 -m pytest tests` 通过，结果：`99 passed`。
- `cd backend; py -3.11 -m compileall app` 通过。
- `cd frontend; node ./node_modules/typescript/bin/tsc --noEmit` 通过。
- `cd frontend; node ./node_modules/eslint/bin/eslint.js app --ext .ts,.tsx` 通过。

## 受限验证

- `cd frontend; npm run build` 执行两次均超时，分别约 124 秒和 304 秒，未返回编译错误文本。
- 为避免影响既有本地服务，额外启动 `next dev --port 3332` 做页面可达性检查；该进程长期停在 `Starting...`，已终止并清理临时日志。
- 因 Next 本地运行环境卡在启动阶段，未完成浏览器手动验收；前端已通过 TypeScript 与 ESLint 静态校验。

## 安全记录

- 未写入真实 API Key、token、cookie 或数据库密码。
- 未修改 `.env`。
- 前端仅调用项目后端 API，不读取或展示第三方密钥。
- 缺少百炼 Key 时，前端会将 `BAILIAN_NOT_CONFIGURED` 映射为“请先在服务器 .env 配置 DASHSCOPE_API_KEY”。

## 后续建议

- 在可正常运行 Next 的环境中补做 `/companies` 与 `/products` 浏览器验收。
- 若后续需要保存 `target_users`、`selling_points`、`risk_notes` 历史记录，建议新增独立 AI 生成记录表或 JSON 字段，不要塞入单条关键词表。
