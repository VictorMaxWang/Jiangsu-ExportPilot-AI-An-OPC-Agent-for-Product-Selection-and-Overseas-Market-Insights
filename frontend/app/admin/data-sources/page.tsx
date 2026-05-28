import { PageHeader } from "../../_components/PageHeader";
import { PlaceholderPanel } from "../../_components/PlaceholderPanel";
import { ProviderStatusDashboard } from "../_components/ProviderStatusDashboard";

export default function DataSourcesPage() {
  const requireAdminPassword = process.env.APP_ENV === "production";

  return (
    <div>
      <PageHeader
        eyebrow="Data Sources"
        title="数据源能力状态"
        description="这里只显示配置状态，不显示密钥；生产环境需要 Admin Password，前端不会持久化保存密码。"
      />
      <PlaceholderPanel title="实时状态">
        <ProviderStatusDashboard requireAdminPassword={requireAdminPassword} />
      </PlaceholderPanel>
    </div>
  );
}
