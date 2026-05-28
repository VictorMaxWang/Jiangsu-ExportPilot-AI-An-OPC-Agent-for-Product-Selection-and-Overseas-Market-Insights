import { PageHeader } from "../../_components/PageHeader";
import { PlaceholderPanel } from "../../_components/PlaceholderPanel";
import { ProviderStatusDashboard } from "../_components/ProviderStatusDashboard";

export default function DataSourcesPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Data Sources"
        title="数据源能力状态"
        description="以后端安全接口为准展示当前数据源能力，P0 provider 可逐项测试，后续扩展 provider 仅返回待注册状态。"
      />
      <PlaceholderPanel title="实时状态">
        <ProviderStatusDashboard />
      </PlaceholderPanel>
    </div>
  );
}
