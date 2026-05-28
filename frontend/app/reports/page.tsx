import { ReportsWorkspace } from "./_components/ReportsWorkspace";

type ReportsPageProps = {
  searchParams?: {
    analysis_id?: string;
  };
};

export default function ReportsPage({ searchParams }: ReportsPageProps) {
  return <ReportsWorkspace initialAnalysisId={searchParams?.analysis_id ?? ""} />;
}
