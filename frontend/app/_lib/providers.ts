import type { ProviderStatus } from "../_components/ProviderStatusBadge";

export type ProviderGroup = "current" | "future";
export type ProviderPriority = "P0" | "P1" | "P2";

export type ProviderCatalogItem = {
  id: string;
  name: string;
  group: ProviderGroup;
  priority: ProviderPriority;
  capabilityStatus: ProviderStatus;
  secretStatus: ProviderStatus;
  defaultStatus: ProviderStatus;
  capability: string;
  secretNote: string;
  fallback: string;
  demoRole: string;
};

export const currentDemoProviders: ProviderCatalogItem[] = [
  {
    id: "bailian",
    name: "阿里云百炼 qwen3.6-plus",
    group: "current",
    priority: "P0",
    capabilityStatus: "integrated",
    secretStatus: "backend_only",
    defaultStatus: "configured",
    capability: "后端调用大模型生成洞察、评分解释、营销草稿和报告段落。",
    secretNote: "仅后端环境读取配置状态，前端不展示 Key。",
    fallback: "未配置时使用 mock/sample AI 文本支撑演示。",
    demoRole: "智能体分析与内容生成核心能力。",
  },
  {
    id: "world-bank",
    name: "World Bank Indicators API",
    group: "current",
    priority: "P0",
    capabilityStatus: "public",
    secretStatus: "public",
    defaultStatus: "integrated",
    capability: "公开宏观指标数据，用于国家市场基础面判断。",
    secretNote: "公开 API，无需密钥。",
    fallback: "可使用 World Bank CSV 样本数据兜底。",
    demoRole: "宏观环境、市场规模和基础风险参考。",
  },
  {
    id: "gdelt",
    name: "GDELT",
    group: "current",
    priority: "P0",
    capabilityStatus: "public",
    secretStatus: "public",
    defaultStatus: "integrated",
    capability: "公开新闻热度、舆情和风险信号。",
    secretNote: "公开 API，无需密钥。",
    fallback: "可使用 GDELT CSV 样本数据兜底。",
    demoRole: "内容热度、新闻风险和市场情绪参考。",
  },
  {
    id: "youtube",
    name: "YouTube Data API v3",
    group: "current",
    priority: "P0",
    capabilityStatus: "integrated",
    secretStatus: "backend_only",
    defaultStatus: "integrated",
    capability: "已接入后端搜索与同步路径，支持 keyword + country 查询。",
    secretNote: "Key 仅由后端读取，禁用或缺失时不影响演示。",
    fallback: "禁用、缺 Key 或调用失败时使用 YouTube Sample 样本。",
    demoRole: "视频内容趋势和海外消费者兴趣信号。",
  },
  {
    id: "etsy",
    name: "Etsy Open API",
    group: "current",
    priority: "P0",
    capabilityStatus: "integrated",
    secretStatus: "backend_only",
    defaultStatus: "integrated",
    capability: "已接入后端活跃 listing 搜索路径。",
    secretNote: "凭据仅用于后端请求头，前端不显示配置值。",
    fallback: "缺失或禁用时使用 Etsy Sample 竞品样本。",
    demoRole: "竞品价格、标题和卖点样本参考。",
  },
  {
    id: "un-comtrade",
    name: "UN Comtrade",
    group: "current",
    priority: "P1",
    capabilityStatus: "optional",
    secretStatus: "optional",
    defaultStatus: "integrated",
    capability: "已接入 no-key-first 非阻塞贸易流查询。",
    secretNote: "可选 Key 仅由后端读取；无 Key 模式优先。",
    fallback: "401、403、429、空响应或禁用时使用贸易样本。",
    demoRole: "进出口贸易规模和品类流向参考。",
  },
  {
    id: "csv-fallback",
    name: "CSV 样本数据兜底",
    group: "current",
    priority: "P0",
    capabilityStatus: "fallback",
    secretStatus: "public",
    defaultStatus: "fallback",
    capability: "比赛演示兜底能力，外部 API 不稳定时仍可完成流程。",
    secretNote: "无需密钥，不包含真实企业敏感信息。",
    fallback: "本身就是兜底数据路径。",
    demoRole: "保证现场可演示的数据底座。",
  },
];

export const futureProviders: ProviderCatalogItem[] = [
  {
    id: "ebay",
    name: "eBay Browse API",
    group: "future",
    priority: "P2",
    capabilityStatus: "future",
    secretStatus: "not_default",
    defaultStatus: "not_default",
    capability: "后续扩展，当前 Demo 不默认启用。",
    secretNote: "需要后端配置后才可接入，前端不读取凭据。",
    fallback: "后续可接入 eBay fallback 样本。",
    demoRole: "未来补充跨境电商竞品和价格信号。",
  },
  {
    id: "rakuten",
    name: "Rakuten Ichiba",
    group: "future",
    priority: "P2",
    capabilityStatus: "future",
    secretStatus: "not_default",
    defaultStatus: "not_default",
    capability: "后续扩展，当前 Demo 不默认启用。",
    secretNote: "需要后端配置后才可接入，前端不读取凭据。",
    fallback: "后续可接入 Rakuten fallback 样本。",
    demoRole: "未来补充日本市场平台商品信号。",
  },
  {
    id: "reddit",
    name: "Reddit API",
    group: "future",
    priority: "P2",
    capabilityStatus: "future",
    secretStatus: "not_default",
    defaultStatus: "not_default",
    capability: "后续扩展，当前 Demo 不默认启用。",
    secretNote: "OAuth 凭据只能由后端读取。",
    fallback: "后续可接入 Reddit fallback 样本。",
    demoRole: "未来补充社群讨论和用户痛点信号。",
  },
];

export const providerCatalog = [...currentDemoProviders, ...futureProviders];
