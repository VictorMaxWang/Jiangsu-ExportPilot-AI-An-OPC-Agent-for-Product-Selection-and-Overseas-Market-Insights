import Link from "next/link";
import { PageHeader } from "../_components/PageHeader";
import { ProductsWorkspace } from "./_components/ProductsWorkspace";

type ProductsPageProps = {
  searchParams?: {
    company_id?: string;
    product_id?: string;
  };
};

export default function ProductsPage({ searchParams }: ProductsPageProps) {
  const initialCompanyId = toPositiveNumber(searchParams?.company_id);
  const initialProductId = toPositiveNumber(searchParams?.product_id);

  return (
    <div>
      <PageHeader
        eyebrow="产品库"
        eyebrowEn="Product Catalog"
        title="产品"
        titleEn="Products"
        description="管理候选产品，分析时结合已支持数据源与 CSV 兜底生成市场机会评分。"
        descriptionEn="Manage candidate products for opportunity scoring with supported data sources and CSV fallback."
      />
      <div className="mb-5">
        <Link
          className="inline-flex rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white"
          href="/products/import"
        >
          智能导入商品
        </Link>
      </div>
      <ProductsWorkspace initialCompanyId={initialCompanyId} initialProductId={initialProductId} />
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
