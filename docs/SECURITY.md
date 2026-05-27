# 安全规范

## 核心原则

本项目涉及多个外部 API 和 AI 服务。所有 Key、Token、Secret、Client Secret、Cookie 和密码都必须按后端密钥处理，不得进入前端、仓库、日志或报告。

## API Key 要求

- 所有 Key 只能在后端环境变量中读取。
- 不允许前端读取、保存、打包、展示或代理传递任何 Key。
- 不允许日志打印 Key、Token、Secret、认证头或完整连接串。
- 不允许提交 `.env`、本地凭证文件、云服务器凭证或浏览器 Cookie。
- 必须提供 `.env.example`，但只能包含变量名和空值或占位说明。
- 管理页只显示“已配置/未配置”，不显示明文、部分明文或可恢复的掩码值。

## 环境变量示例

允许在 `.env.example` 中出现以下占位变量名：

```text
DATABASE_URL=
BAILIAN_API_KEY=
BAILIAN_MODEL=qwen3.6-plus
EBAY_CLIENT_ID=
EBAY_CLIENT_SECRET=
UN_COMTRADE_API_KEY=
RAKUTEN_APP_ID=
YOUTUBE_API_KEY=
ETSY_API_KEY=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
```

禁止在任何文档或代码中写入真实值。

## 前端限制

- 前端只能调用本项目后端 API。
- 前端不得直接请求阿里云百炼、eBay、YouTube、Etsy、Reddit 等需要凭证的第三方 API。
- 前端配置页只能展示后端返回的布尔状态，例如 `{ "bailian": true }`。
- 浏览器 DevTools、页面源码、构建产物和网络响应中不得包含 Key。

## 后端限制

- 后端统一从配置模块读取环境变量。
- 后端对外返回错误时不得包含原始第三方响应中的敏感字段。
- 第三方请求日志必须脱敏，认证头默认不记录。
- 数据库不得保存 API Key。
- AI prompt 和 report 记录不得包含密钥或服务端连接串。

## 日志脱敏规则

日志中禁止出现：

- `Authorization` 头明文。
- API Key、Token、Secret、Cookie。
- 含用户名密码的数据库连接串。
- 第三方完整签名 URL。

如需调试，只记录：

- Provider 名称。
- 请求目标类型，不记录完整敏感 URL。
- HTTP 状态码。
- 耗时。
- 脱敏后的错误类型。

## `.env` 与 `.env.example`

- `.env`：本地私有文件，必须加入 `.gitignore`。
- `.env.example`：可提交文件，只放变量名、空值、示例枚举或说明。
- 部署环境：通过腾讯云服务器环境变量、Docker Compose 私有 env 文件或 Secret 管理方式配置。

## 配置状态接口

管理页所需配置状态接口只允许返回：

```json
{
  "bailian": "configured",
  "world_bank": "public",
  "gdelt": "public",
  "ebay": "not_configured"
}
```

禁止返回明文、前后缀掩码、长度、哈希或任何可用于推断 Key 的内容。

## 泄露处理

如果发现密钥被写入仓库或日志：

1. 立即停止相关任务。
2. 在对应 `docs/status/Txx_xxx.md` 记录泄露位置和影响范围，不写入密钥明文。
3. 从代码和文档中移除敏感内容。
4. 通知总控线程轮换密钥。
5. 补充测试或检查，防止再次泄露。
