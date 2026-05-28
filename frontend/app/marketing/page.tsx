import { Suspense } from "react";
import { PageHeader } from "../_components/PageHeader";
import { MarketingWorkspace } from "./_components/MarketingWorkspace";

export default function MarketingPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Marketing"
        title="Marketing content generator"
        description="Generate English ecommerce titles, bullet points, SEO keywords, short video scripts, Pinterest keywords, and listing advice through the backend Bailian qwen3.6-plus service."
      />
      <Suspense fallback={<div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-600">Loading marketing workspace</div>}>
        <MarketingWorkspace />
      </Suspense>
    </div>
  );
}
