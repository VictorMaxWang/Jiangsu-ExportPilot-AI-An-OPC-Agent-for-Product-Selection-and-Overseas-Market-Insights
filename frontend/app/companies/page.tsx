import { PageHeader } from "../_components/PageHeader";
import { CompaniesWorkspace } from "./_components/CompaniesWorkspace";

type CompaniesPageProps = {
  searchParams?: {
    company_id?: string;
    intake?: string;
  };
};

export default function CompaniesPage({ searchParams }: CompaniesPageProps) {
  const initialCompanyId = toPositiveNumber(searchParams?.company_id);
  const intakeConfirmed = searchParams?.intake === "confirmed";

  return (
    <div>
      <PageHeader
        eyebrow="企业录入"
        eyebrowEn="Company Intake"
        title="企业"
        titleEn="Companies"
        description="录入江苏制造企业基础信息，供产品分析、机会评分、营销生成和出海报告复用。"
        descriptionEn="Manage company profiles used by product analysis, opportunity scoring, marketing generation, and export reports."
      />
      <CompaniesWorkspace initialCompanyId={initialCompanyId} intakeConfirmed={intakeConfirmed} />
    </div>
  );
}

function toPositiveNumber(value: string | undefined): number | null {
  if (!value) {
    return null;
  }
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}
