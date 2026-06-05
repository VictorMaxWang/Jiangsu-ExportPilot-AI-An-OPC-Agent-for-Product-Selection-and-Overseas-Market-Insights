"use client";

import Link from "next/link";
import { AgentStepCard } from "./_components/AgentStepCard";
import { FallbackNotice } from "./_components/FallbackNotice";
import { useI18n } from "./_components/LanguageProvider";
import { PlaceholderPanel } from "./_components/PlaceholderPanel";
import { ProviderStatusBadge } from "./_components/ProviderStatusBadge";
import { currentDemoProviders, futureProviders } from "./_lib/providers";

export default function HomePage() {
  const { text } = useI18n();
  const workflowSteps = [
    {
      title: text("上传截图/链接", "Upload screenshots or links"),
      description: text("从淘宝、京东、拼多多等商品截图或单个公开链接开始，避免把密钥或平台账号暴露到前端。", "Start from product screenshots or a single public product URL without exposing keys or platform accounts in the frontend."),
    },
    {
      title: text("Qwen 识别", "Qwen recognition"),
      description: text("后端调用百炼 Qwen 视觉/文本能力，提取品名、材质、价格、卖点和证据来源。", "The backend calls Bailian Qwen vision/text capabilities to extract product names, material, price, selling points, and evidence."),
    },
    {
      title: text("产品草稿", "Product draft"),
      description: text("人工复核低置信度字段，确认后进入正式产品库，保留截图/链接证据边界。", "Review low-confidence fields, confirm into the catalog, and keep screenshot/link evidence boundaries."),
    },
    {
      title: text("出海分析", "Export analysis"),
      description: text("选择目标市场后，工作流融合公开 API、CSV 兜底、竞品样本、趋势内容和 AI 解释。", "After target-market selection, the workflow combines public APIs, CSV fallback, competitor samples, trend content, and AI explanations."),
    },
    {
      title: text("看板/报告", "Dashboard and reports"),
      description: text("用看板讲清楚机会排序、风险与来源，再生成可复核的出海报告。", "Use dashboards to explain opportunity ranking, risks, and sources, then generate reviewable export reports."),
    },
  ];

  return (
    <div className="grid gap-8">
      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-panel">
        <div className="grid gap-8 p-6 md:grid-cols-[1.08fr_0.92fr] md:p-10">
          <div>
            <p className="text-sm font-semibold text-jade">{text("截图/链接到出海报告", "From product intake to export report")}</p>
            <h1 className="mt-4 text-4xl font-semibold tracking-normal text-ink sm:text-5xl">
              {text("苏品智航", "Jiangsu ExportPilot")}
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-7 text-slate-600">
              {text(
                "面向江苏制造企业的 AI 出海选品工作台：上传商品截图或链接，由后端 Qwen 识别生成产品草稿，确认后启动海外市场分析，并沉淀看板、营销文案和出海报告。",
                "An AI export product-selection workspace for Jiangsu manufacturers: upload product screenshots or URLs, let backend Qwen recognition create product drafts, confirm them, then run overseas market analysis and produce dashboards, copy, and reports.",
              )}
            </p>
            <p className="mt-5 rounded-lg bg-river/5 px-4 py-3 text-sm font-semibold leading-6 text-ink ring-1 ring-river/20">
              {text(
                "主流程：上传截图/链接 → Qwen 识别 → 产品草稿 → 出海分析 → 看板/报告",
                "Workflow: upload screenshots/URLs → Qwen recognition → product draft → export analysis → dashboard/reports",
              )}
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/products/import"
                className="rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#12566d]"
              >
                {text("上传截图或链接", "Upload screenshots or URL")}
              </Link>
              <Link
                href="/analysis/run"
                className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-ink transition hover:bg-slate-50"
              >
                {text("运行出海分析", "Run export analysis")}
              </Link>
              <Link
                href="/reports"
                className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-ink transition hover:bg-slate-50"
              >
                {text("查看示例报告", "View Sample Reports")}
              </Link>
            </div>
          </div>
          <div className="rounded-lg bg-slate-50 p-5">
            <h2 className="text-base font-semibold text-ink">{text("出海主路径", "Primary export path")}</h2>
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
        <PlaceholderPanel title={text("当前 Demo 数据源", "Current Demo Data Sources")}>
          <div className="grid gap-3">
            {currentDemoProviders.map((provider) => (
              <div key={provider.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-slate-50 px-4 py-3">
                <span className="font-medium text-ink">{provider.name}</span>
                <ProviderStatusBadge status={provider.capabilityStatus} />
              </div>
            ))}
          </div>
        </PlaceholderPanel>
        <PlaceholderPanel title={text("后续扩展", "Future Extensions")}>
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
        <PlaceholderPanel title={text("机会评分", "Opportunity Scoring")}>
          {text("基于宏观指标、新闻风险、内容热度、竞品样本、贸易样本与 CSV 兜底数据生成可解释评分。", "Generate explainable scores from macro indicators, news risk, content momentum, competitor samples, trade samples, and CSV fallback data.")}
        </PlaceholderPanel>
        <PlaceholderPanel title={text("营销生成", "Marketing Generation")}>
          {text("百炼生成商品标题、卖点、广告文案、短视频脚本和社媒内容草稿，前端不直接调用模型或第三方 API。", "Bailian generates product titles, selling points, ad copy, short video scripts, and social content drafts. The frontend never calls model or third-party APIs directly.")}
        </PlaceholderPanel>
        <PlaceholderPanel title={text("出海报告", "Export Report")}>
          {text("生成中英双语出海报告，包含评分理由、来源摘要、百炼营销文案草稿与风险提示。", "Generate bilingual export reports with scoring rationale, source summaries, Bailian marketing drafts, and risk notes.")}
        </PlaceholderPanel>
      </div>

      <FallbackNotice
        source="csv"
        title={text("CSV 样本数据兜底", "CSV Sample Fallback")}
        description={text("外部 API 禁用、缺少后端密钥或现场网络不稳定时，演示仍可使用样本数据完成分析、看板和报告流程。", "When external APIs are disabled, backend keys are missing, or the live network is unstable, sample data still supports analysis, dashboards, and reports.")}
      />
    </div>
  );
}
