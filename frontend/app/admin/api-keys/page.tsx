import { PageHeader } from "../../_components/PageHeader";
import { PlaceholderPanel } from "../../_components/PlaceholderPanel";
import { ProviderStatusDashboard } from "../_components/ProviderStatusDashboard";

export default function DataSourceStatusPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Backend Data Providers"
        title="数据源能力状态"
        description="只展示后端 provider 的能力状态、默认启用情况和安全测试结果；页面不展示任何凭据值、片段、长度或哈希。"
      />
      <PlaceholderPanel title="Provider 状态">
        <ProviderStatusDashboard />
      </PlaceholderPanel>
    </div>
  );
}
