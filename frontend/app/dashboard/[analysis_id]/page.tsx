import Link from "next/link";
import { EmptyState } from "../../_components/EmptyState";
import { DashboardDetailWorkspace } from "../_components/DashboardDetailWorkspace";

type DashboardDetailPageProps = {
  params: {
    analysis_id: string;
  };
};

export default function DashboardDetailPage({ params }: DashboardDetailPageProps) {
  const analysisId = Number(params.analysis_id);
  if (!Number.isInteger(analysisId) || analysisId <= 0) {
    return (
      <EmptyState
        title="分析编号无效"
        description="请从运行分析页打开一次有效的市场看板。"
        action={
          <Link className="rounded-md bg-river px-4 py-2 text-sm font-semibold text-white" href="/analysis/run">
            运行分析
          </Link>
        }
      />
    );
  }
  return <DashboardDetailWorkspace analysisId={analysisId} />;
}
