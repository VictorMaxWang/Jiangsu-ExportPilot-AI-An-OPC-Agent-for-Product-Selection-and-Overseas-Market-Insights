import { PageHeader } from "../../_components/PageHeader";
import { ProductImportWorkspace } from "./_components/ProductImportWorkspace";

type ProductImportPageProps = {
  searchParams?: {
    company_id?: string;
  };
};

export default function ProductImportPage({ searchParams }: ProductImportPageProps) {
  const initialCompanyId = toPositiveNumber(searchParams?.company_id);

  return (
    <div>
      <PageHeader
        eyebrow="产品库"
        eyebrowEn="Product Intake"
        title="智能商品导入"
        titleEn="Smart Product Intake"
        description="通过用户主动提供的商品截图或单个国内商品链接生成产品草稿，人工确认后进入正式产品列表。"
        descriptionEn="Generate product drafts from user-provided screenshots or single domestic product links, then confirm them into the product catalog."
      />
      <ProductImportWorkspace initialCompanyId={initialCompanyId} />
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
