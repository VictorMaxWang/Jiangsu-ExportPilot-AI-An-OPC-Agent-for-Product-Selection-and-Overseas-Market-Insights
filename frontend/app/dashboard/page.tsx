import Link from "next/link";
import { redirect } from "next/navigation";
import { EmptyState } from "../_components/EmptyState";
import { FallbackNotice } from "../_components/FallbackNotice";
import { MetricCard } from "../_components/MetricCard";
import { PageHeader } from "../_components/PageHeader";

type DashboardPageProps = {
  searchParams?: {
    analysis_id?: string;
  };
};

const metrics = [
  { label: "已接入主流程", value: "5步", helperText: "导入、草稿、分析、看板、报告" },
  { label: "目标市场样例", value: "8", helperText: "用于比赛演示讲解" },
  { label: "看板输出", value: "4类", helperText: "评分、国家、价格带、趋势来源" },
  { label: "兜底数据集", value: "5", helperText: "CSV/样本兜底路径可用" },
];

export default function DashboardPage({ searchParams }: DashboardPageProps) {
  const analysisId = Number(searchParams?.analysis_id);
  if (Number.isInteger(analysisId) && analysisId > 0) {
    redirect(`/dashboard/${analysisId}`);
  }

  return (
    <div>
      <PageHeader
        eyebrow="市场看板"
        eyebrowEn="Dashboard"
        title="看板"
        titleEn="Dashboard"
        description="看板用于复核一次已完成的出海分析：机会评分、国家推荐、竞品价格区间、内容趋势、风险提示和数据来源会集中展示。"
        descriptionEn="Dashboards review a completed export analysis: opportunity scores, country recommendations, competitor price ranges, content trends, risks, and data sources."
      />
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} {...metric} />
        ))}
      </div>
      <div className="mt-5">
        <EmptyState
          title="请先运行一次分析"
          description="建议路径：先智能导入商品，确认产品草稿，再运行分析；完成后系统会带着 analysis_id 打开本次市场看板。"
          action={
            <div className="flex flex-wrap justify-center gap-2">
              <Link className="rounded-md bg-river px-4 py-2 text-sm font-semibold text-white" href="/analysis/run">
                运行分析
              </Link>
              <Link className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-ink" href="/products/import">
                智能导入
              </Link>
            </div>
          }
        />
      </div>
      <div className="mt-5">
        <FallbackNotice
          source="sample"
          title="Demo 数据说明"
          description="当前 Demo 使用公开 API、缓存、样本数据与 CSV 兜底。竞品样本不代表真实销量，仅作为价格与内容信号。"
        />
      </div>
    </div>
  );
}
