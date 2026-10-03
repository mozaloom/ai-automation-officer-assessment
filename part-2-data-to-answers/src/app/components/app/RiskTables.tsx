import type { DashboardData } from "@/lib/api/types";

const head = "py-2 text-xs font-semibold uppercase tracking-wide text-text-gray";

function pill(pct: number) {
  const tone = pct >= 40 ? "bg-red-50 text-red-700" : pct >= 25 ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700";
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums ${tone}`}>{pct.toFixed(0)}%</span>;
}

export function AtRiskProducts({ rows }: { rows: DashboardData["at_risk_products"] }) {
  if (!rows.length) return <div className="py-10 text-center text-sm text-text-gray">Nothing is at risk for these filters.</div>;
  return (
    <div className="-mx-4 overflow-x-auto sm:mx-0">
      <table className="w-full text-sm">
        <thead><tr className="border-b border-gray-100"><th className={`${head} px-4 text-start sm:px-0`}>Product</th><th className={`${head} hidden text-start sm:table-cell`}>Category</th><th className={`${head} text-end`}>Low</th><th className={`${head} text-end`}>Out</th><th className={`${head} px-4 text-end sm:px-0`}>At risk</th></tr></thead>
        <tbody className="divide-y divide-gray-100">
          {rows.map((r) => (
            <tr key={r.product_name} className="transition-colors hover:bg-gray-50">
              <td className="max-w-[180px] truncate px-4 py-3 font-medium text-text-dark sm:px-0">{r.product_name}</td>
              <td className="hidden py-3 text-text-gray sm:table-cell">{r.category}</td>
              <td className="py-3 text-end tabular-nums text-amber-600">{r.low_stock}</td>
              <td className="py-3 text-end tabular-nums text-red-500">{r.out_of_stock}</td>
              <td className="px-4 py-3 text-end sm:px-0">{pill(r.at_risk_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AtRiskStores({ rows }: { rows: DashboardData["at_risk_stores"] }) {
  if (!rows.length) return <div className="py-10 text-center text-sm text-text-gray">Nothing is at risk for these filters.</div>;
  return (
    <div className="-mx-4 overflow-x-auto sm:mx-0">
      <table className="w-full text-sm">
        <thead><tr className="border-b border-gray-100"><th className={`${head} px-4 text-start sm:px-0`}>Store</th><th className={`${head} hidden text-start sm:table-cell`}>City</th><th className={`${head} text-end`}>Low</th><th className={`${head} text-end`}>Out</th><th className={`${head} px-4 text-end sm:px-0`}>Listings</th></tr></thead>
        <tbody className="divide-y divide-gray-100">
          {rows.map((r) => (
            <tr key={r.store_name} className="transition-colors hover:bg-gray-50">
              <td className="max-w-[200px] truncate px-4 py-3 font-medium text-text-dark sm:px-0">{r.store_name}</td>
              <td className="hidden py-3 text-text-gray sm:table-cell">{r.city}</td>
              <td className="py-3 text-end tabular-nums text-amber-600">{r.low_stock}</td>
              <td className="py-3 text-end tabular-nums text-red-500">{r.out_of_stock}</td>
              <td className="px-4 py-3 text-end tabular-nums text-text-gray sm:px-0">{r.listings}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
