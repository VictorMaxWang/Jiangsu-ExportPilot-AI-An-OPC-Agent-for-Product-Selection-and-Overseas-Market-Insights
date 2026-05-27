import Link from "next/link";
import { PlaceholderPanel } from "./_components/PlaceholderPanel";

const workflowSteps = [
  "Register Jiangsu manufacturing companies and product lines.",
  "Import sample CSV data or connect normalized public market signals.",
  "Run opportunity scoring with fallback data and backend AI services.",
  "Review dashboards and export overseas expansion reports.",
];

export default function HomePage() {
  return (
    <div className="grid gap-8">
      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-panel">
        <div className="grid gap-8 p-6 md:grid-cols-[1.2fr_0.8fr] md:p-10">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-jade">
              AI export opportunity platform
            </p>
            <h1 className="mt-4 text-4xl font-semibold tracking-normal text-ink sm:text-5xl">
              苏品智航 / Jiangsu ExportPilot
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-7 text-slate-600">
              A competition demo for product selection, overseas market insight, AI-assisted
              marketing copy, and expansion report workflows for Jiangsu manufacturers.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/analysis/run"
                className="rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#12566d]"
              >
                Run analysis
              </Link>
              <Link
                href="/dashboard"
                className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-ink transition hover:bg-slate-50"
              >
                View dashboard
              </Link>
            </div>
          </div>
          <div className="rounded-lg bg-slate-50 p-5">
            <h2 className="text-base font-semibold text-ink">Demo workflow</h2>
            <ol className="mt-4 grid gap-3">
              {workflowSteps.map((step, index) => (
                <li key={step} className="flex gap-3 text-sm leading-6 text-slate-600">
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-md bg-white text-xs font-semibold text-river ring-1 ring-slate-200">
                    {index + 1}
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      <div className="grid gap-5 md:grid-cols-3">
        <PlaceholderPanel title="Market signals">
          World Bank, trade, marketplace, video, social, and CSV fallback signals will be normalized
          by backend data clients.
        </PlaceholderPanel>
        <PlaceholderPanel title="Opportunity scoring">
          Product-market fit, demand, competition, logistics, and channel readiness can be surfaced
          as explainable scores.
        </PlaceholderPanel>
        <PlaceholderPanel title="Report export">
          Expansion reports will combine scorecards, market rationale, sample copy, and source
          summaries.
        </PlaceholderPanel>
      </div>
    </div>
  );
}
