# API 数据源规划

本项目采用“后端统一接入 + 标准化输出 + CSV fallback”的数据源策略。所有需要凭据的数据源只能由后端从环境变量读取；前端不得接收、展示、保存或转发任何第三方 API Key、Secret、Token 或 Cookie。

## 2026-05-27 状态纠正

根据真实 API 可用状态，MVP 数据源分级调整如下：

- P0：Alibaba Cloud Bailian `qwen3.6-plus`、World Bank Indicators API、GDELT、YouTube Data API v3、Etsy Open API、CSV fallback。
- P1：UN Comtrade，R09 已接入，采用 no-key-first 策略；只有在公开调用返回 401、403、429 或明确要求 subscription key 时，才尝试可选 `UN_COMTRADE_API_KEY`。
- P2：eBay Browse API、Rakuten Ichiba、Reddit API，作为后续扩展，不阻塞 MVP 主流程。

## 数据源总览

| 优先级 | 数据源 | 当前状态 | 认证方式 | 默认策略 | Fallback |
| --- | --- | --- | --- | --- | --- |
| P0 | Alibaba Cloud Bailian `qwen3.6-plus` | T04 已完成后端接入 | `DASHSCOPE_API_KEY`，兼容 `BAILIAN_API_KEY` | 默认启用，未配置时返回安全错误或 mock/sample 输出 | 预置 AI 示例文本 |
| P0 | World Bank Indicators API | 可用 | 无需 Key | 默认启用 | `data/fallback/world_bank_*.csv` |
| P0 | GDELT | 可用 | 无需 Key | 默认启用 | `data/fallback/gdelt_*.csv` |
| P0 | YouTube Data API v3 | R07 已接入 | `YOUTUBE_DATA_API_KEY` | 默认启用，缺 Key 或 `ENABLE_YOUTUBE=false` 时 fallback | `data/seed/content_trends.csv` YouTube Sample |
| P0 | Etsy Open API | R08 已完成后端接入 | `ETSY_KEYSTRING` + `ETSY_SHARED_SECRET` 作为 `x-api-key` | 默认启用，缺 Key 或 `ENABLE_ETSY=false` 时 fallback | `data/seed/competitor_samples.csv` Etsy Sample |
| P0 | CSV fallback | T03 已完成 | 无需 Key | 始终可用 | 不适用 |
| P1 | UN Comtrade | R09 已接入 | no-key-first，可选 `UN_COMTRADE_API_KEY` | 非阻塞增强 | `data/seed/trade_samples.csv` |
| P2 | eBay Browse API | 暂无 Key | `EBAY_CLIENT_ID`、`EBAY_CLIENT_SECRET` | 默认不启用 | `data/fallback/ebay_*.csv` |
| P2 | Rakuten Ichiba | 暂无 Key | `RAKUTEN_APP_ID`，兼容 `RAKUTEN_APPLICATION_ID` | 默认不启用 | `data/fallback/rakuten_*.csv` |
| P2 | Reddit API | 暂无 Key | `REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET` | 默认不启用 | `data/fallback/reddit_*.csv` |

## P0 数据源

### Alibaba Cloud Bailian `qwen3.6-plus`

- 用途：市场洞察摘要、机会评分解释、风险提示、营销文案和报告段落生成。
- 后端变量：优先读取 `DASHSCOPE_API_KEY`，兼容 `BAILIAN_API_KEY`；模型默认 `BAILIAN_MODEL=qwen3.6-plus`。
- 接入状态：T04 已完成统一后端调用服务，前端不得直接调用 Bailian。
- 安全要求：不返回、不打印、不记录 Key、认证头或第三方原始敏感响应。
- Fallback：未配置或调用失败时使用 mock/sample 文本，并明确标记数据来源。

### World Bank Indicators API

- 用途：目标国家 GDP、人口、互联网普及率、进口相关指标等宏观信号。
- 认证方式：公开 API，无需 Key。
- 标准化输出：国家、年份、指标、数值、单位、来源。
- Fallback：读取 `data/fallback/world_bank_*.csv`。

### GDELT

- 用途：新闻热度、舆情趋势、市场关注度和潜在风险信号。
- 认证方式：公开 API，无需 Key。
- 标准化输出：关键词、国家/语言、时间窗口、新闻数量、主题、情绪或风险摘要。
- Fallback：读取 `data/fallback/gdelt_*.csv`。

### YouTube Data API v3

- 用途：关键词视频热度、内容趋势、频道与互动信号。
- 后端变量：`YOUTUBE_DATA_API_KEY`。
- 接入策略：P0 真实接入任务；仅后端读取 Key，前端只调用本项目后端 API。
- 标准化输出：视频标题、频道、发布时间、观看数、点赞数、关键词、链接。
- Fallback：读取 `data/seed/content_trends.csv` 中的 `YouTube Sample`；Key 缺失、`ENABLE_YOUTUBE=false`、限额或接口失败时自动启用。

### Etsy Open API

- 用途：设计、手工、家居、礼品等消费品趋势与竞品信号。
- 后端变量：`ETSY_KEYSTRING` 和 `ETSY_SHARED_SECRET`；后端组合为 `x-api-key`，不返回、不打印、不透传到前端。
- 接入策略：P0 真实接入任务；只在后端使用凭据。
- 标准化输出：商品标题、价格、币种、店铺、类目、标签、链接。
- Fallback：读取 `data/seed/competitor_samples.csv` 中的 `Etsy Sample` / `Etsy` 行；Key 缺失、`ENABLE_ETSY=false`、限额或接口失败时自动启用。

### CSV fallback

- 用途：保证无网络、无 Key、限流或第三方异常时仍能完成比赛演示。
- 当前状态：T03 已完成种子 CSV 和导入 API。
- 数据位置：`data/seed/` 和后续 `data/fallback/`。
- 响应要求：后端响应必须标记来源，例如 `api`、`csv_fallback`、`mock_ai`。

## P1 数据源

### UN Comtrade

- 用途：HS 编码或品类维度的进出口贸易趋势。
- 策略：先进行无 Key 公开调用；若返回 401、403、429 或明确要求 subscription key，再尝试可选 `UN_COMTRADE_API_KEY`。
- 约束：不得作为 MVP 主流程的强依赖；失败时必须回落到 CSV fallback 或跳过增强字段。
- 标准化输出：报告国、伙伴国、年份、贸易方向、品类编码、贸易额、数量。
- Fallback：读取 `data/seed/trade_samples.csv`，用于现场 Demo 兜底。

## P2 后续扩展

### eBay Browse API

- 当前状态：暂无 Key，不作为 MVP 阻塞项。
- 后端变量：`EBAY_CLIENT_ID`、`EBAY_CLIENT_SECRET`。
- 后续用途：跨境平台商品价格、竞品、类目和销售线索。
- Fallback：读取 `data/fallback/ebay_*.csv`。

### Rakuten Ichiba

- 当前状态：暂无 Key，不作为 MVP 阻塞项。
- 后端变量：优先 `RAKUTEN_APP_ID`，兼容 `RAKUTEN_APPLICATION_ID`。
- 后续用途：日本市场商品价格、标题、评分、评论和类目信号。
- Fallback：读取 `data/fallback/rakuten_*.csv`。

### Reddit API

- 当前状态：暂无 Key，不作为 MVP 阻塞项。
- 后端变量：`REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET`。
- 后续用途：社区讨论、用户痛点、需求描述和热门话题。
- Fallback：读取 `data/fallback/reddit_*.csv`。
