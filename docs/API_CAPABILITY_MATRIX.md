# API Capability Matrix

| provider | current_status | requires_key | key_available | mvp_priority | default_enabled | fallback | notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Alibaba Cloud Bailian `qwen3.6-plus` | T04 已接入 | yes | yes | P0 | yes, when configured | mock/sample AI text | 后端优先读取 `DASHSCOPE_API_KEY`，兼容 `BAILIAN_API_KEY`。 |
| World Bank Indicators API | 可用 | no | n/a | P0 | yes | `data/fallback/world_bank_*.csv` | 公开 API，用于宏观指标。 |
| GDELT | 可用 | no | n/a | P0 | yes | `data/fallback/gdelt_*.csv` | 公开 API，用于新闻热度、舆情和风险信号。 |
| YouTube Data API v3 | R07 已接入 | yes | yes | P0 | yes, disabled/missing-key fallback | `data/seed/content_trends.csv` YouTube Sample | 后端只读取 `YOUTUBE_DATA_API_KEY`；`ENABLE_YOUTUBE=false` 禁用真实调用；keyword+country 使用 24 小时缓存保护 quota。 |
| Etsy Open API | R08 已接入 | yes | yes | P0 | yes, disabled/missing-key fallback | `data/seed/competitor_samples.csv` Etsy Sample | 后端使用 `ETSY_KEYSTRING` 和 `ETSY_SHARED_SECRET` 组合为 `x-api-key`；不使用 OAuth token。 |
| CSV fallback | T03 已完成 | no | n/a | P0 | yes | n/a | 比赛演示兜底能力，必须保持可用。 |
| UN Comtrade | R09 已接入 | optional | optional | P1 | yes as no-key-first, non-blocking | `data/seed/trade_samples.csv` | 先无 Key 调用；401/403/429 或明确要求 subscription key 后再尝试可选 `UN_COMTRADE_API_KEY`。 |
| eBay Browse API | 暂无 Key | yes | no | P2 | no | `data/fallback/ebay_*.csv` | 后续扩展，环境变量为 `EBAY_CLIENT_ID`、`EBAY_CLIENT_SECRET`。 |
| Rakuten Ichiba | 暂无 Key | yes | no | P2 | no | `data/fallback/rakuten_*.csv` | 后续扩展，优先 `RAKUTEN_APP_ID`，兼容 `RAKUTEN_APPLICATION_ID`。 |
| Reddit API | 暂无 Key | yes | no | P2 | no | `data/fallback/reddit_*.csv` | 后续扩展，OAuth 凭据只能由后端读取。 |
