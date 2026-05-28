# API 数据源规划

本项目采用“后端统一接入 + 标准化输出 + seed/CSV fallback”的数据源策略。所有需要凭据的数据源只能由后端从环境变量读取；前端不得接收、展示、保存或转发任何第三方 API Key、Secret、Token 或 Cookie。

## 当前真实状态

- P0：Alibaba Cloud Bailian `qwen3.6-plus`、World Bank Indicators API、GDELT、YouTube Data API v3、Etsy Open API、CSV fallback。
- P1：UN Comtrade，R09 已接入 no-key-first 双模式，可选使用后端环境变量，不能阻塞 MVP 主流程。
- P2：eBay Browse API、Rakuten Ichiba、Reddit API 是 future provider；当前无 runtime client，不作为比赛 MVP 阻塞项。

## 数据源总览

| 优先级 | 数据源 | 当前状态 | 认证方式 | 默认策略 | Fallback |
| --- | --- | --- | --- | --- | --- |
| P0 | Alibaba Cloud Bailian `qwen3.6-plus` | T04 已完成后端接入 | `DASHSCOPE_API_KEY`，兼容 `BAILIAN_API_KEY` | 配置后启用；未配置时返回安全错误或 sample/mock 输出 | sample/mock AI text |
| P0 | World Bank Indicators API | R06 已接入 | 无需 Key | 默认启用 | `data/seed/market_profiles.csv` |
| P0 | GDELT | R06 已接入 | 无需 Key | 默认启用 | `data/seed/content_trends.csv` |
| P0 | YouTube Data API v3 | R07 已接入 | 后端环境变量；状态由安全接口判断 | 默认启用；缺配置、禁用、限流或失败时 fallback | `data/seed/content_trends.csv` YouTube Sample |
| P0 | Etsy Open API | R08 已接入 | 后端环境变量；状态由安全接口判断 | 默认启用；缺配置、禁用、限流或失败时 fallback | `data/seed/competitor_samples.csv` Etsy Sample |
| P0 | CSV fallback | T03/R10 已完成 | 无需 Key | 始终可用 | 不适用 |
| P1 | UN Comtrade | R09 已接入 | no-key-first，可选环境变量 | 非阻塞增强 | `data/seed/trade_samples.csv` |
| P2 | eBay Browse API | future provider | 未实现 runtime client | 默认不启用 | 未实现 runtime fallback |
| P2 | Rakuten Ichiba | future provider | 未实现 runtime client | 默认不启用 | 未实现 runtime fallback |
| P2 | Reddit API | future provider | 未实现 runtime client | 默认不启用 | 未实现 runtime fallback |

## P0/P1 数据源说明

### Alibaba Cloud Bailian `qwen3.6-plus`

- 用途：市场洞察摘要、机会评分解释、风险提示、营销文案和报告段落生成。
- 后端变量：优先读取 `DASHSCOPE_API_KEY`，兼容 `BAILIAN_API_KEY`；模型默认 `BAILIAN_MODEL=qwen3.6-plus`。
- 接入状态：T04 已完成统一后端调用服务，前端不得直接调用 Bailian。
- Fallback：未配置或调用失败时使用 sample/mock 文本，并明确标记数据来源。

### World Bank Indicators API

- 用途：目标国家 GDP、人口、互联网普及率、城市化等宏观信号。
- 认证方式：公开 API，无需 Key。
- Fallback：读取 `data/seed/market_profiles.csv` 并生成标准化指标。

### GDELT

- 用途：新闻热度、舆情趋势、市场关注度和潜在风险信号。
- 认证方式：公开 API，无需 Key。
- Fallback：读取 `data/seed/content_trends.csv` 中的内容趋势样本。

### YouTube Data API v3

- 用途：关键词视频热度、内容趋势、频道与互动信号。
- 后端变量：`YOUTUBE_DATA_API_KEY`。
- 接入状态：R07 已完成后端 provider；真实调用是否可用由后端配置状态、第三方额度和网络状态决定。
- Fallback：读取 `data/seed/content_trends.csv` 中的 `YouTube Sample` 行；缺 Key、禁用、限流或接口失败时自动启用。

### Etsy Open API

- 用途：设计、手工、家居、礼品等消费品趋势与竞品信号。
- 后端变量：`ETSY_KEYSTRING` 和 `ETSY_SHARED_SECRET`。
- 接入状态：R08 已完成后端 provider；真实调用是否可用由后端配置状态、第三方额度和网络状态决定。
- Fallback：读取 `data/seed/competitor_samples.csv` 中的 `Etsy` / `Etsy Sample` 行；缺 Key、禁用、限流或接口失败时自动启用。

### UN Comtrade

- 用途：HS 编码或品类维度的进出口贸易趋势。
- 策略：先进行无 Key 公开调用；若返回 401、403、429 或明确要求 subscription key，再尝试可选环境变量。
- 约束：不得作为 MVP 主流程强依赖；失败时必须回落到 CSV fallback 或跳过增强字段。
- Fallback：读取 `data/seed/trade_samples.csv`。

### CSV/seed fallback

- 用途：保证无网络、无 Key、限流或第三方异常时仍能完成比赛演示。
- 当前数据位置：`data/seed/market_profiles.csv`、`product_catalog.csv`、`content_trends.csv`、`competitor_samples.csv`、`trade_samples.csv`、`user_discussions.csv`。
- 响应要求：后端响应必须标记来源，例如 `api`、`csv_fallback`、`mock_ai`。

## P2 后续扩展

eBay、Rakuten、Reddit 当前只保留为 future provider。后续接入时必须遵守同一规则：后端读取环境变量、前端只看配置状态、失败时提供明确 fallback 或跳过增强字段。
