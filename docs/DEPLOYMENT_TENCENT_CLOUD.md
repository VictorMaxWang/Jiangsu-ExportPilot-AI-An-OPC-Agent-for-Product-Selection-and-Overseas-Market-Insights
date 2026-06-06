# 腾讯云生产部署指南

本文档面向 `opc.ankangyu.cn` 的腾讯云 CVM 生产/比赛演示部署。默认架构为：

```text
Internet
  -> 腾讯云安全组 80/443
  -> 宿主机 Nginx 或宝塔反向代理
  -> 127.0.0.1:3000 frontend container
  -> 127.0.0.1:8000 backend container
  -> postgres / redis containers, no public ports
```

生产部署使用 `docker-compose.prod.yml`。不要用本地开发 `docker-compose.yml` 对公网部署，因为本地配置会暴露 PostgreSQL 和 Redis 端口。

## 0. 生产能力清单

当前生产演示应覆盖以下能力：

- 多图商品录入：`/products/import` 支持一次上传多张商品截图或产品图，后端合并证据后生成产品草稿，用户确认后再入库。
- 企业照片上传：`/companies/import` 支持上传企业门头、展台、名片、产品目录或资质截图，生成企业草稿，人工确认后才创建正式企业。
- 五大洲目标市场：`/analysis/run` 从后端目标国家目录加载国家，支持亚洲、欧洲、北美、拉美、大洋洲和非洲组合分析。
- 全局聊天：聊天只读取当前企业、产品、分析或报告上下文的脱敏摘要，用于解释报告、数据来源、风险边界和下一步动作。
- 报告版本：聊天修改报告只生成 proposal；用户确认后创建新的 `report_versions` 记录，原版本保留。
- 自动部署：GitHub Actions 可在推送 `main` 后通过 SSH 登录 CVM，执行 `git pull` 和 `bash scripts/deploy_prod.sh` 完成升级。

生产现场话术应强调“可解释、可复核、可人工确认”，不要把 fallback 描述成真实外部平台结果，也不要把报告描述成法律、关税、财务或确定性经营结论。

## 1. 服务器准备

- 推荐 Ubuntu 22.04 LTS 或 24.04 LTS，最低 2 vCPU / 4 GB RAM，建议 40 GB 以上系统盘。
- 腾讯云安全组只开放：
  - `80/tcp`：HTTP，供跳转 HTTPS。
  - `443/tcp`：HTTPS。
  - `22/tcp`：仅允许管理员固定 IP 访问。
- 不要在安全组开放 `3000`、`8000`、`5432`、`6379`。
- DNS 将 `opc.ankangyu.cn` 的 A 记录指向 CVM 公网 IP。
- Docker 官方文档提醒，发布容器端口可能绕过某些主机防火墙规则；生产环境应以腾讯云安全组和最小端口暴露为主。参考 Docker 官方 Ubuntu 安装文档：https://docs.docker.com/engine/install/ubuntu/

## 2. 安装 Docker

使用 Docker 官方 apt 仓库安装 Docker Engine 和 Compose plugin：

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

验证：

```bash
docker --version
docker compose version
sudo systemctl status docker
```

如果当前用户需要直接运行 Docker：

```bash
sudo usermod -aG docker "$USER"
newgrp docker
```

## 3. 上传项目

推荐部署目录：

```bash
sudo mkdir -p /opt/supinzhihang
sudo chown -R "$USER":"$USER" /opt/supinzhihang
cd /opt/supinzhihang
```

上传方式二选一：

```bash
git clone <repository-url> .
```

或从本地同步，排除本地缓存和密钥文件：

```bash
rsync -av --delete \
  --exclude '.git' \
  --exclude '.env' \
  --exclude '.env.*' \
  --exclude 'node_modules' \
  --exclude '.next' \
  --exclude '.venv' \
  --exclude 'storage' \
  --exclude '*.log' \
  ./ user@server:/opt/supinzhihang/
```

`storage/` 是运行时目录，可能包含用户主动上传的商品截图，不要同步到 GitHub、聊天记录、截图材料或公开交付包。

## 4. 配置 `.env`

服务器上创建 `.env`，只在服务器保存，权限设为 `0600`：

```bash
cd /opt/supinzhihang
cp .env.example .env
chmod 600 .env
```

生产至少配置以下变量。示例只写占位符，不要把真实值写入文档、Git、截图或聊天记录。

```text
APP_ENV=production
FRONTEND_URL=https://opc.ankangyu.cn
BACKEND_URL=https://opc.ankangyu.cn
NEXT_PUBLIC_API_BASE_URL=https://opc.ankangyu.cn
CORS_ORIGINS=https://opc.ankangyu.cn
PUBLIC_SITE_ORIGIN=https://opc.ankangyu.cn
ALLOWED_ADMIN_ORIGINS=
ADMIN_AUTH_ENABLED=true
ADMIN_PASSWORD=<server-only-admin-password>

POSTGRES_DB=supinzhihang
POSTGRES_USER=supin_app
POSTGRES_PASSWORD=<strong-postgres-password>
DATABASE_URL=postgresql+psycopg://supin_app:<same-postgres-password>@postgres:5432/supinzhihang

REDIS_URL=redis://redis:6379/0
FRONTEND_BIND_PORT=3000
BACKEND_BIND_PORT=8000

BAILIAN_VISION_ENABLED=false
BAILIAN_VISION_MODEL=
PRODUCT_UPLOAD_DIR=/app/storage/product-intake
MAX_PRODUCT_IMAGE_SIZE_MB=10
COMPANY_UPLOAD_DIR=/app/storage/company-intake
MAX_COMPANY_IMAGE_SIZE_MB=10
ENABLE_DOMESTIC_URL_FETCH=false
DATA_COLLECTION_CONCURRENCY=3
```

注意：

- `POSTGRES_PASSWORD` 必须和 `DATABASE_URL` 中的密码一致。
- `NEXT_PUBLIC_API_BASE_URL` 是前端公开变量，只能写本项目 API 地址，不能写任何第三方 API Key。
- 生产环境不要设置 `ADMIN_AUTH_ENABLED=false`。
- `PRODUCT_UPLOAD_DIR` 必须和 `docker-compose.prod.yml` 中的 `product_uploads` volume 挂载路径一致，默认使用 `/app/storage/product-intake`。
- `MAX_PRODUCT_IMAGE_SIZE_MB` 控制单张商品截图大小，默认 10 MB；Nginx `client_max_body_size` 必须大于该值。
- `COMPANY_UPLOAD_DIR` 必须和 `docker-compose.prod.yml` 中的 `company_uploads` volume 挂载路径一致，默认使用 `/app/storage/company-intake`。
- `MAX_COMPANY_IMAGE_SIZE_MB` 控制单张企业照片大小，默认 10 MB；Nginx `client_max_body_size` 必须同时覆盖商品和企业上传。
- `DATA_COLLECTION_CONCURRENCY` 控制外部数据采集并发，默认 `3`，用于在多国家分析时兼顾速度和第三方接口稳定性。
- `ENABLE_DOMESTIC_URL_FETCH=false` 是生产安全默认值。关闭时单链接解析只做平台和 URL 安全识别，并提示用户上传截图继续分析。

## 5. 配置 API Key

所有第三方 Key 只写入服务器 `.env`，只由后端读取：

```text
DASHSCOPE_API_KEY=<optional-bailian-key>
BAILIAN_API_KEY=
BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
BAILIAN_MODEL=qwen3.6-plus
BAILIAN_VISION_ENABLED=false
BAILIAN_VISION_MODEL=<optional-vision-model>

ENABLE_YOUTUBE=true
YOUTUBE_DATA_API_KEY=<optional-youtube-key>

ENABLE_ETSY=true
ETSY_KEYSTRING=<optional-etsy-keystring>
ETSY_SHARED_SECRET=<optional-etsy-shared-secret>

ENABLE_UN_COMTRADE=true
UN_COMTRADE_API_KEY=<optional-un-comtrade-key>
```

未配置 YouTube、Etsy 或 UN Comtrade Key 时，系统应继续使用 CSV fallback 或公开接口兜底。不要在前端、Nginx、镜像构建参数或日志中传递这些 Key。

智能商品截图识别只由后端调用 Bailian/Qwen。只有同时满足以下条件时才开启真实视觉识别：

- `.env` 中配置了后端专用的 `DASHSCOPE_API_KEY` 或 `BAILIAN_API_KEY`。
- `BAILIAN_VISION_ENABLED=true`。
- `BAILIAN_VISION_MODEL` 指向可用的视觉/多模态模型。

如果视觉模型未启用或不可用，系统会创建低置信度人工草稿，前端提示用户补全后再确认入库。

国内商品链接解析只处理用户主动提交的单个链接，不使用 Cookie、登录态、验证码服务、代理池或模拟登录。登录、验证码、风控、超时、非 HTML、响应过大或结构不可解析时，系统返回 `needs_screenshot` 并提示上传商品截图，不应描述为绕过平台限制。

## 5.1 上传与草稿确认

生产上传目录必须使用 Docker volume 或宿主机持久化目录，不能放在镜像临时层：

```text
product_uploads:/app/storage/product-intake
company_uploads:/app/storage/company-intake
```

商品多图上传约束：

- 前端最多选择 8 张商品图片或截图。
- 后端只接受 PNG、JPEG、WebP 等图片类型，并按 `MAX_PRODUCT_IMAGE_SIZE_MB` 限制单图大小。
- 识别结果必须展示置信度、证据摘录和风险提示；只有用户点击确认后才写入正式产品库。
- 部分图片上传失败时应生成低置信度草稿或错误提示，不应静默忽略。

企业照片上传约束：

- 前端最多选择 4 张企业照片或资料截图。
- 上传前应裁剪手机号、地址、聊天记录、证件号码、订单号和账号头像等隐私信息。
- 企业草稿只保存企业名称、地区、行业、描述、主营产品、目标市场建议、置信度和最小证据摘录。
- 用户确认前不得把 AI 识别结果当成正式企业档案。

运维排查时可以查看文件数量、目录权限和文件类型，但不要把用户上传图片同步到 GitHub、CI 日志、公开演示截图或聊天记录。

## 6. 启动 Docker Compose

首次部署或升级推荐使用脚本：

```bash
cd /opt/supinzhihang
bash scripts/deploy_prod.sh
```

脚本会执行：

- 校验生产 compose。
- 构建前后端镜像。
- 启动 PostgreSQL 和 Redis。
- 迁移前执行数据库备份。
- 运行 `alembic upgrade head`。
- 启动 backend 和 frontend。
- 检查 `http://127.0.0.1:8000/health`。

生产 compose 已为商品截图配置持久化 volume：

```text
product_uploads:/app/storage/product-intake
company_uploads:/app/storage/company-intake
```

这些 volume 用于保存用户主动上传的商品截图和企业照片，容器重建后不会丢失。不要把 volume 内容提交 GitHub；如业务需要保留截图，应把 volume 纳入服务器备份策略，并确保备份访问权限受控。

手动命令：

```bash
docker compose --project-name supinzhihang_prod --env-file .env -f docker-compose.prod.yml config --quiet
docker compose --project-name supinzhihang_prod --env-file .env -f docker-compose.prod.yml build --pull backend frontend
docker compose --project-name supinzhihang_prod --env-file .env -f docker-compose.prod.yml up -d postgres redis
docker compose --project-name supinzhihang_prod --env-file .env -f docker-compose.prod.yml run --rm --no-deps backend alembic upgrade head
docker compose --project-name supinzhihang_prod --env-file .env -f docker-compose.prod.yml run --rm --no-deps --user root backend sh -lc 'mkdir -p /app/storage/product-intake /app/storage/company-intake && chown -R appuser:appuser /app/storage'
docker compose --project-name supinzhihang_prod --env-file .env -f docker-compose.prod.yml up -d --remove-orphans backend frontend
```

不要运行无 `--quiet` 的 `docker compose config` 后复制输出，因为展开后的配置可能包含密钥。

## 7. 配置 Nginx/宝塔反向代理

生产 compose 将前后端绑定到宿主机回环地址：

- frontend：`127.0.0.1:3000`
- backend：`127.0.0.1:8000`

Nginx 示例位于：

```text
docs/nginx/opc.ankangyu.cn.conf
```

转发规则：

- `/` 转发到 `http://127.0.0.1:3000`
- `/api` 和 `/api/` 转发到 `http://127.0.0.1:8000`
- `/health` 转发到 `http://127.0.0.1:8000/health`
- `client_max_body_size 20m` 支持 CSV、商品多图和企业照片上传，并应大于 `.env` 中的 `MAX_PRODUCT_IMAGE_SIZE_MB` 与 `MAX_COMPANY_IMAGE_SIZE_MB`

如果使用宝塔面板，可在站点反向代理中按上述路径配置，或把示例文件中的 location 合并到宝塔生成的站点配置。证书路径由宝塔或腾讯云 SSL 控制台管理，不要提交真实私钥。

## 8. 配置 HTTPS

推荐二选一：

- 宝塔面板申请 Let's Encrypt 证书。
- 腾讯云 SSL 控制台申请证书，并在 Nginx 或宝塔中绑定。

启用：

- HTTP `80` 跳转 HTTPS `443`。
- HTTPS 证书自动续期或到期提醒。
- 稳定运行后再评估是否开启 HSTS。

## 9. 数据库迁移

迁移文件位于 `backend/alembic/`，后端镜像已包含 Alembic 配置。升级时执行：

```bash
docker compose --project-name supinzhihang_prod --env-file .env -f docker-compose.prod.yml run --rm --no-deps backend alembic upgrade head
```

迁移前必须备份数据库。不要在生产环境直接删除 volume 或执行未审查的 downgrade。

## 9.1 聊天与报告版本验收

升级后建议做一次非破坏性验收：

1. 打开任意报告详情页，确认版本列表可见。
2. 通过全局聊天询问“解释这份报告的主要风险和数据来源”。
3. 让聊天生成一条报告修改建议，确认页面显示 proposal，而不是直接覆盖报告。
4. 点击应用后确认新增版本号，旧版本仍可查看。
5. 点击拒绝另一条 proposal，确认只更新 proposal 状态，不产生新版本。

聊天上下文只应包含当前企业、产品、分析和报告的脱敏摘要。不要把 `.env`、API Key、Cookie、认证头或完整数据库连接串复制给聊天。

## 9.2 GitHub Actions 自动部署

推荐的自动部署方式是：GitHub Actions 在 `main` 分支 push 后通过 GitHub-hosted runner 远程 SSH 登录 CVM，在 `/opt/supinzhihang` 中重置到 `origin/main` 并运行生产部署脚本。当前仓库使用 `.github/workflows/deploy.yml`，支持 `push main` 自动触发和 `workflow_dispatch` 手动触发，不使用 self-hosted runner。

服务器侧准备：

```bash
cd /opt/supinzhihang
git remote -v
test -f .env
bash scripts/deploy_prod.sh
```

GitHub 仓库只保存 Action 所需的 Secret 名称，不在仓库写真实值。必需 Repository Secrets：

```text
TENCENT_HOST
TENCENT_PORT
TENCENT_USER
TENCENT_SSH_KEY
```

部署 job 远程执行的核心命令：

```bash
cd /opt/supinzhihang
git fetch origin
git reset --hard origin/main
sed -i 's/\r$//' scripts/*.sh
chmod +x scripts/*.sh
SKIP_BACKUP_BEFORE_MIGRATION=1 bash scripts/deploy_prod.sh
curl http://127.0.0.1:8000/health
curl -I https://opc.ankangyu.cn
curl -sS -X POST https://opc.ankangyu.cn/api/ai/smoke/text -H 'Content-Type: application/json' -d '{}'
```

安全要求：

- 不要把 `.env` 放进 GitHub Actions artifact、日志或缓存。
- 不要在 workflow 中 `echo` Secret。
- 不要在 workflow 或排错记录中输出 API Key、Cookie、管理密码、Authorization header 或数据库连接串。
- 如果部署失败，只粘贴失败阶段、退出码和非敏感日志摘要。
- 本自动部署按比赛演示要求设置 `SKIP_BACKUP_BEFORE_MIGRATION=1`，不会修改服务器 `.env`。

## 10. 查看日志

常用命令：

```bash
docker compose --project-name supinzhihang_prod -f docker-compose.prod.yml ps
docker compose --project-name supinzhihang_prod -f docker-compose.prod.yml logs -f --tail=200 backend
docker compose --project-name supinzhihang_prod -f docker-compose.prod.yml logs -f --tail=200 frontend
docker compose --project-name supinzhihang_prod -f docker-compose.prod.yml logs -f --tail=200 postgres
docker compose --project-name supinzhihang_prod -f docker-compose.prod.yml logs -f --tail=200 redis
```

排查时不要粘贴：

- API Key、Token、Cookie、Authorization 头。
- 完整 `DATABASE_URL`。
- `.env` 内容。
- 带签名或凭证的第三方 URL。

## 11. 备份数据库

推荐使用脚本，默认输出到 `/var/backups/supinzhihang/postgres`：

```bash
cd /opt/supinzhihang
bash scripts/backup_db.sh
```

自定义备份目录：

```bash
BACKUP_DIR=/data/backups/supinzhihang bash scripts/backup_db.sh
```

脚本使用 PostgreSQL custom dump 格式，并用 `pg_restore --list` 校验归档。备份文件权限为 `0600`。

数据库备份不包含 `product_uploads` 和 `company_uploads` volume。若比赛或生产演示需要保留用户上传截图，应单独备份 Docker volume 或宿主机映射目录，并继续遵守“不公开、不提交、不截图泄露”的规则。

## 12. 回滚

代码回滚：

```bash
cd /opt/supinzhihang
git fetch --all
git checkout <previous-known-good-commit-or-tag>
bash scripts/deploy_prod.sh
```

数据库恢复：

```bash
RESTORE_CONFIRM=supinzhihang_prod bash scripts/restore_db.sh /var/backups/supinzhihang/postgres/<backup-file>.dump
```

回滚前记录：

- 当前 Git commit。
- 回滚目标 commit 或 tag。
- 备份文件名。
- `.env` 是否发生过变更，只记录变量名，不记录值。

## 13. 常见问题

### 后端连不上 PostgreSQL

检查 `POSTGRES_PASSWORD` 与 `DATABASE_URL` 中密码是否一致。若 volume 已经初始化过，修改 `.env` 中的 `POSTGRES_PASSWORD` 不会自动改旧数据库密码。

### 前端调用 API 失败

检查：

- `NEXT_PUBLIC_API_BASE_URL=https://opc.ankangyu.cn`
- `CORS_ORIGINS=https://opc.ankangyu.cn`
- Nginx `/api` 是否保留路径前缀并转发到 backend。
- backend health：`curl http://127.0.0.1:8000/health`

### 管理页返回 401

生产默认启用管理认证。确认 `.env` 已配置 `ADMIN_PASSWORD`，前端管理页输入的是同一个密码。不要把该密码写入文档或截图。

### YouTube/Etsy 显示 fallback

对应 Key 缺失、额度不足、网络失败或平台审批限制时会使用 fallback。确认 `.env` 中 provider 开关与 Key 配置，必要时查看 backend 日志，但不要打印 Key。

### 链接解析提示上传截图

这是预期的合规兜底。`ENABLE_DOMESTIC_URL_FETCH=false`、页面需要登录、出现验证码/风控、访问超时、响应过大、非 HTML 或结构不可解析时，系统会返回 `needs_screenshot`。演示时切换到截图导入，不要尝试使用登录态、Cookie、验证码识别、代理池或模拟登录。

### 截图上传失败或 413

检查：

- Nginx `client_max_body_size` 是否大于 `MAX_PRODUCT_IMAGE_SIZE_MB`。
- `.env` 中 `MAX_PRODUCT_IMAGE_SIZE_MB` 或 `MAX_COMPANY_IMAGE_SIZE_MB` 是否设置过低。
- 上传文件是否为 PNG、JPEG 或 WebP。
- 后端 `PRODUCT_UPLOAD_DIR`、`COMPANY_UPLOAD_DIR` 是否与 compose volume 挂载路径一致。

### 聊天没有修改报告

确认聊天返回的是 proposal 卡片。系统设计为“先建议、再确认、后保存版本”，不会直接覆盖当前报告。如果没有 proposal，检查报告详情页是否提供 `report_id` 和当前版本上下文，以及 backend 日志中的非敏感错误码。

### 五大洲国家选择很慢

检查：

- `DATA_COLLECTION_CONCURRENCY` 是否为合理值，例如 `3`。
- 目标国家数量是否超过演示需要；现场建议使用 6 个国家覆盖五大洲。
- provider 是否命中缓存或 CSV fallback。
- 后端日志是否出现第三方限流、超时或网络错误。

### 端口 5432 或 6379 无法访问

这是生产预期。PostgreSQL 和 Redis 不应对公网或宿主机普通端口暴露，只允许容器网络内部访问。

### 生产 build 变慢

Next.js production build 会比 dev server 慢。低配 CVM 上建议保留足够内存和磁盘空间，必要时先在 CI 或本地构建验证。
