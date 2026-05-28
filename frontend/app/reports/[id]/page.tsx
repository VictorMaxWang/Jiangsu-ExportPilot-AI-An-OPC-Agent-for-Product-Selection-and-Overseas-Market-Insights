import { EmptyState } from "../../_components/EmptyState";
import { ReportDetailWorkspace } from "../_components/ReportDetailWorkspace";

type ReportDetailPageProps = {
  params: {
    id: string;
  };
};

export default function ReportDetailPage({ params }: ReportDetailPageProps) {
  const reportId = Number(params.id);
  if (!Number.isInteger(reportId) || reportId < 1) {
    return (
      <EmptyState
        title="Invalid report id"
        description="Open a report from the report list."
      />
    );
  }
  return <ReportDetailWorkspace reportId={reportId} />;
}
