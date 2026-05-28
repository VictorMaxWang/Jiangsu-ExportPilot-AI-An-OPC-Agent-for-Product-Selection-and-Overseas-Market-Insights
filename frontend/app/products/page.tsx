import { PageHeader } from "../_components/PageHeader";
import { ProductsWorkspace } from "./_components/ProductsWorkspace";

export default function ProductsPage() {
  return (
    <div>
      <PageHeader
        eyebrow="产品库 / Product Catalog"
        title="产品 / Products"
        description="管理候选产品，分析时结合已支持数据源与 CSV 兜底生成市场机会评分。"
      />
      <ProductsWorkspace />
    </div>
  );
}
