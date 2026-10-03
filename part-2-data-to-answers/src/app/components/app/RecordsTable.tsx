import type { PosRecord } from "@/lib/api/types";
import { formatDate, formatJod } from "@/lib/format";
import StatusBadge from "./StatusBadge";

const head = "py-2 pe-3 text-start text-xs font-semibold uppercase tracking-wide text-text-gray";

export default function RecordsTable({ records, total, asOf }: { records: PosRecord[]; total: number; asOf: string }) {
  if (!records.length) return null;
  const MAX_ROWS = 25;
  const rows = records.slice(0, MAX_ROWS);
  return (
    <div className="mt-3 rounded-xl border border-gray-100 bg-gray-50/60 p-3" data-testid="records">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs text-text-gray">
        <span className="font-semibold text-text-dark">Matching POS records</span>
        <span>Showing {rows.length} of {total}. Data as of {formatDate(asOf)}.</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead><tr className="border-b border-gray-200"><th className={head}>Store</th><th className={head}>Location</th><th className={head}>Product</th><th className={head}>State</th><th className={`${head} text-end`}>Qty</th><th className={`${head} text-end`}>Price</th><th className={`${head} text-end`}>Updated</th></tr></thead>
          <tbody className="divide-y divide-gray-100">
            {rows.map((r) => (
              <tr key={`${r.store_name}|${r.product_name}|${r.pack_size}`}>
                <td className="py-2 pe-3 font-medium text-text-dark">{r.store_name}</td>
                <td className="py-2 pe-3 text-text-gray">{r.area}, {r.city}</td>
                <td className="py-2 pe-3 text-text-dark">{r.product_name} <span className="text-text-gray">({r.pack_size})</span></td>
                <td className="py-2 pe-3"><StatusBadge status={r.availability_status} /></td>
                <td className="py-2 pe-3 text-end tabular-nums">{r.quantity_on_shelf}</td>
                <td className="whitespace-nowrap py-2 pe-3 text-end tabular-nums">{formatJod(r.shelf_price_jod)}</td>
                <td className="whitespace-nowrap py-2 text-end tabular-nums text-text-gray">{formatDate(r.last_updated)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
