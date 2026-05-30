import { Suspense } from "react";
import { PageHeader } from "../_components/PageHeader";
import { MarketingWorkspace } from "./_components/MarketingWorkspace";

export default function MarketingPage() {
  return (
    <div>
      <PageHeader
        eyebrow="营销生成"
        eyebrowEn="Marketing"
        title="营销文案生成"
        titleEn="Marketing Content Generator"
        description="通过后端百炼 qwen3.6-plus 生成跨境电商标题、卖点、SEO 关键词、短视频脚本、Pinterest 关键词和上架建议。"
        descriptionEn="Generate ecommerce titles, bullet points, SEO keywords, short video scripts, Pinterest keywords, and listing advice through the backend Bailian qwen3.6-plus service."
      />
      <Suspense fallback={<div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-600">正在加载营销工作台</div>}>
        <MarketingWorkspace />
      </Suspense>
    </div>
  );
}
