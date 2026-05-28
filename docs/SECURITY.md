# 安全规范

## 核心原则

本项目涉及多个外部 API 和 AI 服务。所有 Key、Token、Secret、Client Secret、Cookie、数据库密码和云服务凭据都必须按后端密钥处理，不得进入前端、仓库、日志、截图、导出报告或比赛材料。

## API Key 要求

- 所有 Key 只能由后端从环境变量读取。
- 前端不得读取、保存、打包、展示或代理传递任何第三方凭据。
- 不允许日志打印 Key、Token、Secret、认证头、Cookie 或完整敏感连接串。
- 不允许提交 `.env`、本地凭据文件、云服务器凭据或浏览器 Cookie。
- `.env.example` 只能包含变量名、空值或明显本地占位符。
- 管理页只能显示“已配置/未配置/公开 API”等状态，不得显示明文、部分明文、哈希、长度或可恢复掩码。

## 允许出现的环境变量名

以下名称可以出现在 `.env.example`、文档和部署说明中，但只能使用空值或占位符：

```text
DATABASE_URL=
DASHSCOPE_API_KEY=
BAILIAN_API_KEY=
BAILIAN_BASE_URL=
BAILIAN_MODEL=qwen3.6-plus
YOUTUBE_DATA_API_KEY=
ENABLE_YOUTUBE=true
ENABLE_ETSY=true
ENABLE_UN_COMTRADE=true
ETSY_KEYSTRING=
ETSY_SHARED_SECRET=
UN_COMTRADE_API_KEY=
EBAY_CLIENT_ID=
EBAY_CLIENT_SECRET=
RAKUTEN_APP_ID=
RAKUTEN_APPLICATION_ID=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
```

禁止在任何代码、文档、测试、README、前端或状态文件中写入真实值。

## 本地敏感文件

项目目录里可能存在本地凭据材料，例如 `cross_border_api_keys_and_docs.txt`。处理规则：

- 不读取、不复制、不摘要、不输出该类文件内容。
- 不删除用户本地文件。
- 必须通过 `.gitignore` 确保敏感文件不会被 Git 跟踪。
- 如果发现敏感文件已被跟踪，立即停止相关任务，在状态文件中只记录路径、行号和风险类型，不记录真实值。

`.gitignore` 必须覆盖：

```text
.env
.env.*
cross_border_api_keys_and_docs.txt
cross_border_api_env_template.txt
*api_keys*
*secret*
secrets/
```

## 前端限制

- 前端只能调用本项目后端 API。
- 前端不得直接请求 Bailian、YouTube、Etsy、eBay、Rakuten、Reddit 或任何需要凭据的第三方 API。
- 前端不得新增 `NEXT_PUBLIC_*KEY`、`NEXT_PUBLIC_*SECRET`、`NEXT_PUBLIC_*TOKEN` 等公开凭据变量。
- 浏览器 DevTools、页面源码、构建产物和网络响应中不得包含第三方凭据。

## 后端限制

- 后端统一从配置模块读取环境变量。
- 后端对外返回错误时不得包含第三方原始敏感响应、认证头或完整请求 URL。
- 第三方请求日志必须脱敏，认证头默认不记录。
- 数据库不得保存 API Key、Token、Secret 或 Cookie。
- AI prompt、AI 输出、报告和分析记录不得包含密钥或服务端敏感连接串。

## 数据源凭据策略

- Bailian：后端优先使用 `DASHSCOPE_API_KEY`，兼容 `BAILIAN_API_KEY`。
- YouTube：后端使用 `YOUTUBE_DATA_API_KEY`。
- Etsy：后端使用 `ETSY_KEYSTRING` 和 `ETSY_SHARED_SECRET` 组合为 `x-api-key`；`ENABLE_ETSY=false` 时禁用真实调用并使用 CSV fallback。
- UN Comtrade：优先无 Key 调用；`ENABLE_UN_COMTRADE=false` 时直接使用 CSV fallback；仅在 401、403、429 或明确要求 subscription key 时尝试可选 `UN_COMTRADE_API_KEY`。
- eBay、Rakuten、Reddit：当前为 P2 future providers，不作为 MVP 主流程依赖。

## 日志脱敏规则

日志中禁止出现：

- `Authorization` 头明文
- API Key、Token、Secret、Cookie
- 含用户名密码的数据库连接串
- 第三方完整签名 URL

如需调试，只记录：

- Provider 名称
- 请求目标类型，不记录完整敏感 URL
- HTTP 状态码
- 耗时
- 脱敏后的错误类型

## 配置状态接口

管理页所需配置状态接口只允许返回状态枚举，例如：

```json
{
  "bailian": "configured",
  "world_bank": "public",
  "gdelt": "public",
  "youtube": "configured",
  "etsy": "configured",
  "un_comtrade": "optional",
  "ebay": "not_configured"
}
```

禁止返回明文、前后缀掩码、长度、哈希或任何可用于推断凭据的内容。

## 泄露处理

如果发现密钥被写入仓库、日志、截图或报告：

1. 立即停止相关任务。
2. 在对应 `docs/status/Rxx_*.md` 记录泄露位置、行号、风险类型和影响范围，不写入密钥明文。
3. 从代码和文档中移除敏感内容。
4. 通知总控线程轮换相关凭据。
5. 补充扫描或测试，防止再次泄露。
