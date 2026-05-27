import { PageHeader } from "../_components/PageHeader";
import { PlaceholderPanel } from "../_components/PlaceholderPanel";

const products = [
  { name: "Portable power station", category: "Energy storage", market: "EU" },
  { name: "Smart pet feeder", category: "Consumer IoT", market: "North America" },
  { name: "Outdoor folding chair", category: "Light manufacturing", market: "Japan" },
];

export default function ProductsPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Product catalog"
        title="Products"
        description="Manage candidate products before importing demand signals and running market opportunity analysis."
      />
      <PlaceholderPanel title="Candidate products">
        <div className="grid gap-3">
          {products.map((product) => (
            <article
              key={product.name}
              className="grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 sm:grid-cols-[1fr_auto]"
            >
              <div>
                <h2 className="text-base font-semibold text-ink">{product.name}</h2>
                <p className="mt-1 text-sm text-slate-600">{product.category}</p>
              </div>
              <div className="self-start rounded-md bg-white px-3 py-2 text-sm font-medium text-river ring-1 ring-slate-200">
                Target: {product.market}
              </div>
            </article>
          ))}
        </div>
      </PlaceholderPanel>
    </div>
  );
}
