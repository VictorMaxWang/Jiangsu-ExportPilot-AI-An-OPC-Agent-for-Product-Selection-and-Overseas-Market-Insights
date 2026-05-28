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
  { label: "候选产品样本", value: "12", helperText: "Demo seed product coverage" },
  { label: "目标市场样例", value: "8", helperText: "Used for competition walkthrough" },
  { label: "报告草稿样例", value: "3", helperText: "Generated from sample scoring output" },
  { label: "兜底数据集", value: "5", helperText: "CSV/sample fallback paths remain available" },
];

export default function DashboardPage({ searchParams }: DashboardPageProps) {
  const analysisId = Number(searchParams?.analysis_id);
  if (Number.isInteger(analysisId) && analysisId > 0) {
    redirect(`/dashboard/${analysisId}`);
  }

  return (
    <div>
      <PageHeader
        eyebrow="市场看板 / Dashboard"
        title="看板 / Dashboard"
        description="选择一次已完成的智能体分析后，看板会展示机会评分、国家推荐、竞品价格区间、内容趋势、风险提示和数据来源。"
      />
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} {...metric} />
        ))}
      </div>
      <div className="mt-5">
        <EmptyState
          title="请先运行一次分析"
          description="完成智能体分析后，系统会带着 analysis_id 打开本次市场看板。"
          action={
            <Link className="rounded-md bg-river px-4 py-2 text-sm font-semibold text-white" href="/analysis/run">
              进入演示流程
            </Link>
          }
        />
      </div>
      <div className="mt-5">
        <FallbackNotice
          source="sample"
          title="Demo 数据说明"
          description="当前 Demo 使用公开 API、缓存、样本数据与 CSV fallback。竞品样本不代表真实销量，仅作为价格与内容信号。"
        />
      </div>
    </div>
  );
}
