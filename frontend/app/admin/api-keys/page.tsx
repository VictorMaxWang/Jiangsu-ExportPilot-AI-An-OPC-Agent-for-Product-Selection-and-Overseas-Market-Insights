import { PageHeader } from "../../_components/PageHeader";
import { PlaceholderPanel } from "../../_components/PlaceholderPanel";

const providers = [
  "Alibaba Cloud Bailian",
  "eBay Browse API",
  "UN Comtrade",
  "Rakuten Ichiba",
  "YouTube Data API",
  "Etsy Open API",
  "Reddit API",
];

export default function ApiKeysPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Backend configuration"
        title="API keys"
        description="Frontend screens must never expose third-party API keys. This page only shows provider configuration placeholders."
      />
      <PlaceholderPanel title="Provider configuration status">
        <div className="overflow-hidden rounded-lg border border-slate-200">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-4 py-3 font-semibold">Provider</th>
                <th className="px-4 py-3 font-semibold">Frontend status</th>
                <th className="px-4 py-3 font-semibold">Secret handling</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {providers.map((provider) => (
                <tr key={provider}>
                  <td className="px-4 py-3 font-medium text-ink">{provider}</td>
                  <td className="px-4 py-3 text-slate-600">Backend status pending</td>
                  <td className="px-4 py-3 text-slate-600">Server environment only</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </PlaceholderPanel>
    </div>
  );
}
