import { PageHeader } from "../_components/PageHeader";
import { PlaceholderPanel } from "../_components/PlaceholderPanel";

const reportSections = [
  "Executive summary",
  "Product-market scorecard",
  "Demand and competition evidence",
  "AI-generated listing copy",
  "Channel and launch recommendations",
];

export default function ReportsPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Export deliverables"
        title="Reports"
        description="Draft overseas expansion reports that combine structured analysis outputs with reviewer-friendly narratives."
      />
      <PlaceholderPanel title="Report builder placeholder">
        <div className="grid gap-3">
          {reportSections.map((section) => (
            <div key={section} className="flex items-center justify-between rounded-lg bg-slate-50 px-4 py-3">
              <span className="text-sm font-medium text-ink">{section}</span>
              <span className="text-sm text-slate-500">Pending data</span>
            </div>
          ))}
        </div>
      </PlaceholderPanel>
    </div>
  );
}
