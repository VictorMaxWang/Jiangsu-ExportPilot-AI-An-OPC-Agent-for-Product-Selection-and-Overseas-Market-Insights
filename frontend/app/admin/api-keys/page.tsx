import { PageHeader } from "../../_components/PageHeader";
import { PlaceholderPanel } from "../../_components/PlaceholderPanel";
import { ProviderStatusDashboard } from "../_components/ProviderStatusDashboard";

export default function DataSourceStatusPage() {
  const requireAdminPassword = process.env.APP_ENV === "production";

  return (
    <div>
      <PageHeader
        eyebrow="后端能力状态"
        eyebrowEn="Backend Data Providers"
        title="数据源能力状态"
        titleEn="Provider Capability Status"
        description="这里只显示配置状态，不显示密钥；生产环境需要管理员密码，前端不会持久化保存密码。"
        descriptionEn="This page shows configured/not configured only. Production requires an admin password, which is never persisted by the frontend."
      />
      <PlaceholderPanel title="能力状态">
        <ProviderStatusDashboard requireAdminPassword={requireAdminPassword} />
      </PlaceholderPanel>
    </div>
  );
}
