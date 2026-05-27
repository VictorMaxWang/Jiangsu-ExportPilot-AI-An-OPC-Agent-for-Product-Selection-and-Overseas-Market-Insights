# T01 项目脚手架

- 任务编号与名称：T01 项目脚手架
- 负责线程：T01 项目脚手架开发 Agent（scaffold-agent、frontend-agent、backend-agent、reviewer-agent 自检）
- 开始时间：2026-05-26T22:26:08+08:00
- 完成时间：2026-05-26T23:28:37+08:00

## 完成内容

- 创建 Next.js + TypeScript + Tailwind CSS 前端骨架，包含统一布局、导航栏和页面：`/`、`/companies`、`/products`、`/analysis/run`、`/dashboard`、`/reports`、`/admin/api-keys`。
- 创建 FastAPI 后端骨架和分层目录：`api/`、`core/`、`db/`、`models/`、`schemas/`、`services/`、`utils/`。
- 实现 `GET /health`，返回 `{"status":"ok","service":"supinzhihang-backend"}`。
- 创建 Docker Compose 配置，包含 `frontend`、`backend`、`postgres`、`redis`，PostgreSQL 默认库名为 `supinzhihang`。
- 创建 `.env.example`、`.gitignore`、`README.md`、`data/seed/.gitkeep`、`scripts/.gitkeep`，并同时保留用户要求变量名与项目规范中的兼容别名。

## 修改路径

- `.env.example`
- `.gitignore`
- `README.md`
- `docker-compose.yml`
- `frontend/`
- `backend/`
- `data/seed/.gitkeep`
- `scripts/.gitkeep`
- `docs/status/T01_project_scaffold.md`

## 如何启动

前端：

```powershell
cd frontend
npm install
npm run dev -- --hostname 127.0.0.1 --port 3000
```

后端：

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Docker Compose：

```powershell
Copy-Item .env.example .env
docker compose up --build
```

## 验证结果

- `backend`: `python -m pytest tests` 通过，结果 `1 passed`。
- `backend`: 本地启动在 `127.0.0.1:8001` 验证，`GET /health` 返回目标 JSON。默认 `8000` 当时被本机 `Manager.exe` 占用，未强行关闭用户进程。
- `frontend`: `npm run lint` 通过，无 ESLint warnings/errors。
- `frontend`: `npm run build` 通过，所有目标路由均生成静态页面。
- `frontend`: 本地启动在 `127.0.0.1:3000`，首页和 `/companies`、`/products`、`/analysis/run`、`/dashboard`、`/reports`、`/admin/api-keys` 均返回 HTTP 200。
- `docker`: `docker --version` 和 `docker compose version` 未通过，因为本机命令行未安装 Docker 或 Docker 不在 PATH，无法实际执行 `docker compose up --build`。

## 环境变量与安全

- 新增 `.env.example`，只包含空值或本地占位符，没有真实 API Key；百炼、Rakuten、YouTube、Etsy 变量同时提供用户清单名和项目规范别名，后续任务应统一配置读取策略。
- 前端没有读取或暴露第三方 API Key；`NEXT_PUBLIC_API_BASE_URL` 仅用于公开后端地址。
- 后端当前只提供健康检查，未记录密钥、认证头或数据库连接串。

## 遇到的问题

- 本机 npm 直连 registry 下载较慢，首次安装 Next.js 依赖多次超时；已生成可用 `package-lock.json`。
- 本机安装过程中 SWC 二进制包曾因中断安装损坏；验证时通过校验匹配 lockfile 的 tarball 重新替换了本地 `node_modules` 中的生成文件。源码和 lockfile 未依赖该临时修复。
- Codex 内置浏览器连接失败，错误为浏览器客户端信任桥不可用；已用 HTTP 请求验证前端页面和路由可访问。

## 后续任务建议

- T02 在安装 Docker Desktop 的环境中复验 `docker compose up --build`。
- T03/T04 增加数据库连接、SQLAlchemy 基础配置和配置读取测试。
- T05 在当前前端壳上继续补充真实组件、API client 和更完整的页面状态。
