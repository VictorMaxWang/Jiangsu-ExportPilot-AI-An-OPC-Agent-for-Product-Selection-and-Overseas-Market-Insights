import { PageHeader } from "../_components/PageHeader";
import { PlaceholderPanel } from "../_components/PlaceholderPanel";

const metrics = [
  { label: "Products tracked", value: "12" },
  { label: "Markets reviewed", value: "8" },
  { label: "Reports drafted", value: "3" },
  { label: "Fallback datasets", value: "5" },
];

export default function DashboardPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Insight workspace"
        title="Dashboard"
        description="A unified view for opportunity scores, demand indicators, channel readiness, and report progress."
      />
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map((metric) => (
          <section key={metric.label} className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
            <p className="text-sm font-medium text-slate-500">{metric.label}</p>
            <p className="mt-3 text-3xl font-semibold text-ink">{metric.value}</p>
          </section>
        ))}
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <PlaceholderPanel title="Score trend placeholder">
          Chart integration will use ECharts behind a reusable wrapper once backend scoring data is
          available.
        </PlaceholderPanel>
        <PlaceholderPanel title="Market watchlist placeholder">
          Target market rows will show normalized signals, score movement, and recommended next
          actions.
        </PlaceholderPanel>
      </div>
    </div>
  );
}
