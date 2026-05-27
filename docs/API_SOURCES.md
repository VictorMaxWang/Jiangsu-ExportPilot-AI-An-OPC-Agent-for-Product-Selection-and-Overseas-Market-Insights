# API 数据源规划

本项目采用“后端统一接入 + 标准化输出 + CSV fallback”的数据源策略。所有需要凭证的数据源只能由后端读取环境变量后调用。

## 数据源总览

| 数据源 | 用途 | 认证方式 | MVP 策略 | Fallback |
| --- | --- | --- | --- | --- |
| 阿里云百炼 `qwen3.6-plus` | AI 洞察、评分解释、文案、报告段落 | 后端环境变量 `BAILIAN_API_KEY` | 必接，支持 mock 输出 | 使用预置 AI 样例文本 |
| World Bank | 国家宏观经济、人口、GDP、贸易环境指标 | 通常公开 API | 必接基础指标 | CSV 国家指标样例 |
| GDELT | 新闻、舆情、市场关注度、风险信号 | 通常公开 API | 必接关键词搜索 | CSV 新闻趋势样例 |
| eBay Browse API | 商品价格、竞品、跨境平台需求 | OAuth/Client 凭证 | 可接 MVP 重点品类 | CSV 商品样例 |
| UN Comtrade | 贸易流向、品类进出口数据 | API Key 或公开额度 | 接入核心查询或 CSV | CSV 贸易样例 |
| Rakuten Ichiba | 日本市场商品和价格信号 | Application ID | 可选接入 | CSV 日本商品样例 |
| YouTube Data API | 视频内容趋势、关键词热度 | API Key | 可选接入 | CSV 视频趋势样例 |
| Etsy Open API | 设计、手工、家居类商品趋势 | API Key/OAuth | 可选接入 | CSV 商品趋势样例 |
| Reddit API | 社区需求、痛点、讨论热词 | OAuth Client | 可选接入 | CSV 讨论样例 |
| CSV fallback | 演示兜底数据 | 无 | 必备 | 本地样本数据 |

## 阿里云百炼 qwen3.6-plus

- 目标：生成市场洞察摘要、机会评分解释、风险提示、营销文案和报告段落。
- 后端变量：`BAILIAN_API_KEY`、`BAILIAN_MODEL`。
- 安全要求：只在后端调用；不向前端返回 Key；不记录完整认证请求。
- 标准化输出：`summary`、`opportunities`、`risks`、`copywriting`、`report_sections`。
- Fallback：当未配置 Key 或调用失败时，使用 mock/样例文本，并在响应中标记 `source: "fallback"`。

## World Bank

- 目标：获取目标国家的 GDP、人口、互联网普及率、进口相关指标等宏观信号。
- 认证方式：公开 API 优先。
- 标准化输出：国家、年份、指标名、指标值、单位、来源。
- Fallback：读取 `data/fallback/world_bank_*.csv`。

## GDELT

- 目标：根据产品关键词和目标市场获取新闻热度、舆情趋势和潜在风险信号。
- 认证方式：公开 API 优先。
- 标准化输出：关键词、国家/语言、时间窗口、新闻数量、主题、情绪或风险摘要。
- Fallback：读取 `data/fallback/gdelt_*.csv`。

## eBay Browse API

- 目标：获取跨境平台商品价格、标题、类目、竞品数量和销售线索。
- 认证方式：后端使用 Client ID/Secret 或 OAuth 流程。
- 后端变量：`EBAY_CLIENT_ID`、`EBAY_CLIENT_SECRET`。
- 标准化输出：平台、商品标题、价格、币种、国家、类目、链接、抓取时间。
- Fallback：读取 `data/fallback/ebay_*.csv`。

## UN Comtrade

- 目标：获取 HS 编码或品类维度的进出口贸易趋势。
- 认证方式：API Key 或公开额度。
- 后端变量：`UN_COMTRADE_API_KEY`。
- 标准化输出：报告国、伙伴国、年份、贸易方向、品类编码、贸易额、数量。
- Fallback：读取 `data/fallback/un_comtrade_*.csv`。

## Rakuten Ichiba

- 目标：补充日本市场商品价格、标题、评论和类目信号。
- 认证方式：Application ID。
- 后端变量：`RAKUTEN_APP_ID`。
- 标准化输出：平台、商品标题、价格、评分、评论数、类目、链接。
- Fallback：读取 `data/fallback/rakuten_*.csv`。

## YouTube Data API

- 目标：根据关键词获取视频内容热度、标题、频道和观看互动信号。
- 认证方式：API Key。
- 后端变量：`YOUTUBE_API_KEY`。
- 标准化输出：视频标题、频道、发布时间、观看数、点赞数、关键词、链接。
- Fallback：读取 `data/fallback/youtube_*.csv`。

## Etsy Open API

- 目标：获取手工、设计、家居、礼品类商品趋势，对江苏轻工和消费品有参考价值。
- 认证方式：API Key 或 OAuth。
- 后端变量：`ETSY_API_KEY`。
- 标准化输出：商品标题、价格、币种、店铺、类目、标签、链接。
- Fallback：读取 `data/fallback/etsy_*.csv`。

## Reddit API

- 目标：获取社区讨论、用户痛点、需求描述和热门话题。
- 认证方式：OAuth Client。
- 后端变量：`REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET`。
- 标准化输出：社区、标题、摘要、互动数、发布时间、关键词、链接。
- Fallback：读取 `data/fallback/reddit_*.csv`。

## CSV Fallback

- 目标：保证比赛现场在无网络、无 Key、API 限流或接口异常时仍可完整演示。
- 输入位置：`data/samples/`。
- 标准化位置：`data/fallback/` 或数据库 `source_snapshots`。
- 响应标记：后端必须返回数据来源字段，例如 `api`、`csv_fallback`、`mock_ai`。
- 演示要求：至少准备一个江苏制造产品样例和两个目标市场样例。
