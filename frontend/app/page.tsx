import Link from "next/link";
import { AgentStepCard } from "./_components/AgentStepCard";
import { FallbackNotice } from "./_components/FallbackNotice";
import { PlaceholderPanel } from "./_components/PlaceholderPanel";
import { ProviderStatusBadge } from "./_components/ProviderStatusBadge";
import { currentDemoProviders, futureProviders } from "./_lib/providers";

const workflowSteps = [
  {
    title: "企业产品输入",
    description: "录入江苏制造企业、产业带优势、候选产品和目标市场。",
  },
  {
    title: "多源数据融合",
    description: "汇总 World Bank、GDELT、YouTube、Etsy、可选 UN Comtrade 与 CSV 样本。",
  },
  {
    title: "智能体分析",
    description: "后端调用阿里云百炼 qwen3.6-plus，生成洞察、解释和营销草稿。",
  },
  {
    title: "机会评分",
    description: "输出需求、竞争、宏观环境、内容热度、贸易信号和风险因子。",
  },
  {
    title: "营销生成",
    description: "生成标题、卖点、广告文案、短视频脚本和社媒内容草稿。",
  },
  {
    title: "出海报告",
    description: "整理成可复制的比赛演示报告和企业初步决策材料。",
  },
];

export default function HomePage() {
  return (
    <div className="grid gap-8">
      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-panel">
        <div className="grid gap-8 p-6 md:grid-cols-[1.2fr_0.8fr] md:p-10">
          <div>
            <p className="text-sm font-semibold text-jade">AI 出海选品平台 / AI Export Opportunity Platform</p>
            <h1 className="mt-4 text-4xl font-semibold tracking-normal text-ink sm:text-5xl">
              苏品智航 / Jiangsu ExportPilot
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-7 text-slate-600">
              面向江苏制造企业出海的 AI 选品与海外市场洞察智能体。整合产品信息、
              CSV 样本、World Bank、GDELT、YouTube、Etsy 与可选 UN Comtrade 数据，
              由后端调用阿里云百炼 qwen3.6-plus 生成评分解释、营销草稿与出海报告。
            </p>
            <p className="mt-5 rounded-lg bg-slate-50 px-4 py-3 text-sm font-semibold leading-6 text-ink ring-1 ring-slate-200">
              主流程：企业产品输入 → 多源数据融合 → 智能体分析 → 机会评分 → 营销生成 → 出海报告
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/analysis/run"
                className="rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#12566d]"
              >
                进入演示流程
              </Link>
              <Link
                href="/reports"
                className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-ink transition hover:bg-slate-50"
              >
                查看示例报告
              </Link>
            </div>
          </div>
          <div className="rounded-lg bg-slate-50 p-5">
            <h2 className="text-base font-semibold text-ink">Demo workflow</h2>
            <ol className="mt-4 grid gap-3">
              {workflowSteps.map((step, index) => (
                <li key={step.title}>
                  <AgentStepCard
                    title={step.title}
                    description={step.description}
                    status="complete"
                    stepNumber={index + 1}
                  />
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        <PlaceholderPanel title="当前 Demo 数据源">
          <div className="grid gap-3">
            {currentDemoProviders.map((provider) => (
              <div key={provider.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-slate-50 px-4 py-3">
                <span className="font-medium text-ink">{provider.name}</span>
                <ProviderStatusBadge status={provider.capabilityStatus} />
              </div>
            ))}
          </div>
        </PlaceholderPanel>
        <PlaceholderPanel title="后续扩展">
          <div className="grid gap-3">
            {futureProviders.map((provider) => (
              <div key={provider.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-slate-50 px-4 py-3">
                <span className="font-medium text-ink">{provider.name}</span>
                <ProviderStatusBadge status="future" />
              </div>
            ))}
          </div>
        </PlaceholderPanel>
      </div>

      <div className="grid gap-5 md:grid-cols-3">
        <PlaceholderPanel title="机会评分">
          基于宏观指标、新闻风险、内容热度、竞品样本、贸易样本与 CSV 兜底数据生成可解释评分。
        </PlaceholderPanel>
        <PlaceholderPanel title="营销生成">
          百炼生成商品标题、卖点、广告文案、短视频脚本和社媒内容草稿，前端不直接调用模型或第三方 API。
        </PlaceholderPanel>
        <PlaceholderPanel title="出海报告">
          生成中英双语出海报告，包含评分理由、来源摘要、百炼营销文案草稿与风险提示。
        </PlaceholderPanel>
      </div>

      <FallbackNotice
        source="csv"
        title="CSV 样本数据兜底"
        description="外部 API 禁用、缺少后端密钥或现场网络不稳定时，演示仍可使用样本数据完成分析、看板和报告流程。"
      />
    </div>
  );
}
