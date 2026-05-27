# T03 Demo 样本数据与 CSV 导入

- 任务编号与名称：T03 Demo 样本数据与 CSV 导入
- 负责线程：T03 Demo 样本数据与 CSV 导入开发 Agent
- 开始时间：2026-05-27T08:35:00+08:00
- 完成时间：2026-05-27T09:03:25+08:00

## 完成内容

- 创建 `data/seed/` Demo CSV 种子数据：
  - `product_catalog.csv`：10 条南通家纺、家居、宠物家居产品，覆盖任务指定产品。
  - `competitor_samples.csv`：84 条竞品样本，覆盖 eBay、Amazon Sample、Shopee Sample、Temu Sample、Etsy Sample、Rakuten Sample。
  - `market_profiles.csv`：US、GB、JP、AU、SG 5 个市场画像。
  - `trade_samples.csv`：40 条家纺 HS 编码贸易样本，覆盖 5 个国家和 2023/2024 年。
  - `content_trends.csv`：52 条内容趋势样本，覆盖 YouTube Sample、TikTok Sample、Pinterest Sample、Reddit Sample。
  - `user_discussions.csv`：30 条匿名海外用户讨论样本。
- 新增 CSV 导入服务 `backend/app/services/importers/csv_importer.py`：
  - 支持产品、竞品、市场画像、贸易样本、内容趋势、用户讨论导入。
  - 默认读取 `data/seed/`，并限制自定义 `file_name` 不能逃逸该目录。
  - 支持 `insert` 与 `validate` 模式。
  - 提供行级字段错误，包含行号、字段、错误说明和原始值。
  - 整批校验通过后统一写库，失败时不写入。
- 新增导入 API：
  - `POST /api/import/products`
  - `POST /api/import/competitors`
  - `POST /api/import/market-profiles`
  - `POST /api/import/trade-samples`
  - `POST /api/import/content-trends`
  - `POST /api/import/user-discussions`
- 新增导入请求与响应 schema，并注册导入路由。
- 新增后端测试 `backend/tests/test_import_api.py`，覆盖种子数据、导入成功、校验模式和错误提示。

## 修改路径

- `data/seed/product_catalog.csv`
- `data/seed/competitor_samples.csv`
- `data/seed/market_profiles.csv`
- `data/seed/trade_samples.csv`
- `data/seed/content_trends.csv`
- `data/seed/user_discussions.csv`
- `backend/app/api/imports.py`
- `backend/app/api/router.py`
- `backend/app/schemas/imports.py`
- `backend/app/schemas/__init__.py`
- `backend/app/services/__init__.py`
- `backend/app/services/importers/__init__.py`
- `backend/app/services/importers/csv_importer.py`
- `backend/tests/test_import_api.py`
- `docs/status/T03_seed_data_import.md`

## 验证结果

- `py -3.11 -m pytest tests` 通过，结果 `12 passed`。
- `py -3.11 -m compileall app` 通过。

## 未完成或受限说明

- 未修改数据库模型或 Alembic 迁移，复用 T02 已有模型。
- 由于现有表缺少唯一约束，导入暂不做去重或 upsert；重复导入会重复插入样本。
- `market_profiles.csv` 的 `notes` 字段仅保留在 CSV 中，导入时不落库；定性等级按 `low=1`、`medium=2`、`high=3` 转为 `market_indicators` 数值，年份固定为 2025。
- `user_discussions.csv` 当前映射到 `content_trends`，并标记 `content_style="user_discussion"`；后续若增加独立用户讨论表，可替换落库目标。

## 安全记录

- 未写入真实 API Key、token、cookie 或其他凭证。
- 未修改 `.env`。
- 导入 API 限制读取 `data/seed/` 内 CSV，避免任意本地文件读取。

## 后续建议

- T07/T08 可在此基础上扩展上传文件、导入批次记录、原始行 `raw_payload` 和去重策略。
- T12 可复用 `content_trends` 与 `user_discussions` 样本作为社媒 fallback。
