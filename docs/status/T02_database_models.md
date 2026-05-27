# T02 数据库模型与迁移基础

- 任务编号与名称：T02 数据库模型与迁移基础
- 负责线程：T02 数据库模型与迁移开发 Agent
- 开始时间：2026-05-27T07:45:00+08:00
- 完成时间：2026-05-27T08:16:11+08:00

## 完成内容

- 配置 SQLAlchemy 2 数据库基础层：`Base`、命名约定、engine、`SessionLocal`、`get_db()`。
- 扩展后端配置读取，`Settings.database_url` 支持 `DATABASE_URL` 和 `SUPIN_DATABASE_URL`。
- 引入 Alembic，新增首个迁移 `20260527_0001_create_database_models.py`。
- 创建数据库模型：`companies`、`products`、`product_keywords`、`api_credentials`、`competitor_items`、`market_indicators`、`trade_stats`、`news_items`、`content_trends`、`analysis_runs`、`opportunity_scores`、`reports`。
- 为主要模型创建 Pydantic v2 `Create`、`Update`、`Read`、`ListItem` schema。
- 创建基础 CRUD services：`companies`、`products`、`competitor_items`、`reports`、`analysis_runs`。
- 新增基础 API：`GET /api/companies`、`POST /api/companies`、`GET /api/products`、`POST /api/products`。
- 保留现有 `GET /health` 行为不变。
- `api_credentials.encrypted_value` 仅存在于 Create/Update schema，不在 Read/List schema 中返回。

## 修改路径

- `backend/requirements.txt`
- `backend/Dockerfile`
- `backend/alembic.ini`
- `backend/alembic/`
- `backend/app/core/config.py`
- `backend/app/db/`
- `backend/app/models/`
- `backend/app/schemas/`
- `backend/app/services/`
- `backend/app/api/`
- `backend/tests/test_database_api.py`
- `docs/status/T02_database_models.md`

## 验证结果

- `py -3.11 -m pip install -r requirements.txt` 通过。
- `py -3.11 -m pytest tests` 通过，结果 `5 passed`。
- `py -3.11 -m compileall app` 通过。
- `DATABASE_URL=sqlite:// py -3.11 -m alembic upgrade head` 通过。
- 使用临时 SQLite 文件执行 Alembic 迁移并检查表名，确认生成：
  `alembic_version`、`analysis_runs`、`api_credentials`、`companies`、`competitor_items`、`content_trends`、`market_indicators`、`news_items`、`opportunity_scores`、`product_keywords`、`products`、`reports`、`trade_stats`。
- 临时迁移检查数据库 `.t02_migration_check.db` 已删除。

## 未完成或受限验证

- 本机 `python` 指向 MSYS Python，缺少 pip；实际使用 `py -3.11` 完成依赖安装和验证。
- 本机未安装 Docker 或 Docker 不在 PATH，`docker --version` 和 `docker compose version` 均失败，因此未能实际运行 PostgreSQL 容器验证。
- 当前代码路径使用 `postgresql+psycopg://...` 的 `DATABASE_URL` 连接 PostgreSQL；需要在安装 Docker/PostgreSQL 的环境中补跑：

```powershell
docker compose up -d postgres
docker compose run --rm backend alembic upgrade head
docker compose exec postgres psql -U supin_app -d supinzhihang -c "\dt"
```

## 安全记录

- 未写入真实 API Key、token、cookie 或数据库密码。
- 未修改 `.env`。
- 未修改 `frontend/`。

## 后续建议

- T06 产品录入任务可直接复用 `companies`、`products` API。
- T08-T12 数据源任务可复用 `competitor_items`、`market_indicators`、`trade_stats`、`news_items`、`content_trends` 模型。
- T14-T17 可复用 `analysis_runs`、`opportunity_scores`、`reports` 模型与 CRUD service。
