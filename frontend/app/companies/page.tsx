import { PageHeader } from "../_components/PageHeader";
import { PlaceholderPanel } from "../_components/PlaceholderPanel";

const companyFields = ["Company name", "City", "Industry cluster", "Export readiness", "Primary contact"];

export default function CompaniesPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Company intake"
        title="Companies"
        description="Capture basic manufacturer profiles that downstream product, scoring, and report flows can reuse."
      />
      <div className="grid gap-5 lg:grid-cols-[0.85fr_1.15fr]">
        <PlaceholderPanel title="New company placeholder">
          <form className="grid gap-4" aria-label="Company profile placeholder form">
            {companyFields.map((field) => (
              <label key={field} className="grid gap-2">
                <span className="text-sm font-medium text-slate-700">{field}</span>
                <input
                  className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
                  placeholder={`Enter ${field.toLowerCase()}`}
                  type="text"
                />
              </label>
            ))}
            <button
              className="mt-2 rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white"
              type="button"
            >
              Save draft
            </button>
          </form>
        </PlaceholderPanel>
        <PlaceholderPanel title="Company list">
          <div className="overflow-hidden rounded-lg border border-slate-200">
            <table className="w-full border-collapse text-left text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-semibold">Company</th>
                  <th className="px-4 py-3 font-semibold">Cluster</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                <tr>
                  <td className="px-4 py-3 font-medium text-ink">Sample Jiangsu Manufacturer</td>
                  <td className="px-4 py-3 text-slate-600">Smart appliances</td>
                  <td className="px-4 py-3 text-slate-600">Draft</td>
                </tr>
              </tbody>
            </table>
          </div>
        </PlaceholderPanel>
      </div>
    </div>
  );
}
