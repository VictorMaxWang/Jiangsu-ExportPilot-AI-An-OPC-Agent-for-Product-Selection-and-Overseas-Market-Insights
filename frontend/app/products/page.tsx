import Link from "next/link";
import { PageHeader } from "../_components/PageHeader";
import { ProductsWorkspace } from "./_components/ProductsWorkspace";

type ProductsPageProps = {
  searchParams?: {
    company_id?: string;
    product_id?: string;
    intake?: string;
  };
};

export default function ProductsPage({ searchParams }: ProductsPageProps) {
  const initialCompanyId = toPositiveNumber(searchParams?.company_id);
  const initialProductId = toPositiveNumber(searchParams?.product_id);
  const intakeConfirmed = searchParams?.intake === "confirmed";

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
      <div className="mb-5 flex flex-col gap-3 rounded-lg border border-river/20 bg-river/5 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-ink">用截图或商品链接快速生成产品草稿</p>
          <p className="mt-1 text-sm text-slate-600">适合导入淘宝、拼多多、京东等用户主动提供的商品素材。</p>
        </div>
        <Link
          className="inline-flex w-fit rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white shadow-sm"
          href="/products/import"
        >
          智能导入商品
        </Link>
      </div>
      {intakeConfirmed ? (
        <div className="mb-5 flex flex-col gap-3 rounded-lg border border-jade/30 bg-jade/10 p-4 text-sm text-jade sm:flex-row sm:items-center sm:justify-between">
          <span className="font-semibold">已入库，可进入智能体分析</span>
          <Link className="w-fit rounded-md bg-jade px-3 py-2 text-sm font-semibold text-white" href="/analysis/run">
            进入智能体分析
          </Link>
        </div>
      ) : null}
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
