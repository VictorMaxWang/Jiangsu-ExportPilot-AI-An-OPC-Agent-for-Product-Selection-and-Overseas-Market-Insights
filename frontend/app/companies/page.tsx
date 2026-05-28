import { PageHeader } from "../_components/PageHeader";
import { CompaniesWorkspace } from "./_components/CompaniesWorkspace";

export default function CompaniesPage() {
  return (
    <div>
      <PageHeader
        eyebrow="企业录入 / Company Intake"
        title="企业 / Companies"
        description="录入江苏制造企业基础信息，供产品分析、机会评分、营销生成和出海报告复用。"
      />
      <CompaniesWorkspace />
    </div>
  );
}
