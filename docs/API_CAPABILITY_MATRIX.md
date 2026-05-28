# API Capability Matrix

| provider | current_status | requires_key | key_available | mvp_priority | default_enabled | fallback | notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Alibaba Cloud Bailian `qwen3.6-plus` | T04 已接入 | yes | environment-dependent | P0 | yes, when configured | sample/mock AI text | 后端优先读取 `DASHSCOPE_API_KEY`，兼容 `BAILIAN_API_KEY`；前端不得直接调用。 |
| World Bank Indicators API | R06 已接入 | no | n/a | P0 | yes | `data/seed/market_profiles.csv` | 公开 API，用于宏观市场指标；API 失败时从 seed 生成 fallback 指标。 |
| GDELT | R06 已接入 | no | n/a | P0 | yes | `data/seed/content_trends.csv` | 公开 API，用于新闻热度、舆情和风险信号；API 失败时使用内容趋势样本。 |
| YouTube Data API v3 | R07/Q02 已接入 | yes | status-api/environment-dependent | P0 | yes, disabled/missing-key fallback | `data/seed/content_trends.csv` YouTube Sample | 后端读取 `YOUTUBE_DATA_API_KEY`；`force_live=true` 可绕过缓存做真实搜索测试。 |
| Etsy Open API | R08/Q02 已接入 | yes | status-api/environment-dependent | P0 | yes, disabled/missing-key/listing-access fallback | `data/seed/competitor_samples.csv` Etsy Sample | 后端读取 `ETSY_KEYSTRING` 和 `ETSY_SHARED_SECRET`；`openapi-ping` 成功但 listings 受 OAuth/审批限制时明确标记并继续使用 CSV fallback。 |
| CSV fallback | T03/R10 已完成 | no | n/a | P0 | yes | n/a | 比赛演示兜底能力，样本集中在 `data/seed/`。 |
| UN Comtrade | R09/Q02 已接入 | optional | status-api/environment-dependent | P1 | yes as no-key-first, non-blocking | `data/seed/trade_samples.csv` | 先无 Key 调用；仅 401/403 且存在可选环境变量时带 Key 重试，失败则明确使用贸易样本 fallback。 |
| eBay Browse API | future provider | yes | no runtime client | P2 | no | no runtime fallback | 当前不作为 MVP 阻塞项；如需展示相关样本，应使用合成 seed 数据而非声明真实接入。 |
| Rakuten Ichiba | future provider | yes | no runtime client | P2 | no | no runtime fallback | 当前不作为 MVP 阻塞项。 |
| Reddit API | future provider | yes | no runtime client | P2 | no | no runtime fallback | 当前不作为 MVP 阻塞项。 |
