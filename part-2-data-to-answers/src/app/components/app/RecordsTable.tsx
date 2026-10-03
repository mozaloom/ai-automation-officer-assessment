"use client";

import type { PosRecord } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/I18nProvider";
import StatusBadge from "./StatusBadge";

const head = "py-2 pe-3 text-start text-xs font-medium text-text-gray";
const MAX_ROWS = 25;

/** The records an answer was built from, shown under it so the reader can check every number. */
export default function RecordsTable({ records, total, asOf }: { records: PosRecord[]; total: number; asOf: string }) {
  const { t, locale, label, pack, jod, date, number } = useI18n();
  if (!records.length) return null;
  const rows = records.slice(0, MAX_ROWS);
  const r = t.records;
  return (
    <div className="enter mt-4 border-t border-line pt-3" data-testid="records">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className="text-sm font-semibold text-text-dark">{r.title}</h3>
        <p className="text-xs text-text-gray">{r.showing(rows.length, total, date(asOf))}</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead><tr className="border-b border-line"><th className={head}>{r.store}</th><th className={head}>{r.location}</th><th className={head}>{r.product}</th><th className={head}>{r.state}</th><th className={`${head} text-end`}>{r.quantity}</th><th className={`${head} text-end`}>{r.price}</th><th className={`${head} pe-0 text-end`}>{r.updated}</th></tr></thead>
          <tbody className="divide-y divide-line">
            {rows.map((row) => (
              <tr key={`${row.store_name}|${row.product_name}|${row.pack_size}`}>
                <td className="py-2 pe-3 font-medium text-text-dark">{label("store_name", row.store_name)}</td>
                <td className="py-2 pe-3 text-text-gray">{label("area", row.area)}{locale === "ar" ? "، " : ", "}{label("city", row.city)}</td>
                <td className="py-2 pe-3 text-text-dark">{label("product_name", row.product_name)} <span className="text-text-gray">({pack(row.pack_size)})</span></td>
                <td className="py-2 pe-3"><StatusBadge status={row.availability_status} /></td>
                <td className="py-2 pe-3 text-end tabular-nums">{number(row.quantity_on_shelf)}</td>
                <td className="whitespace-nowrap py-2 pe-3 text-end tabular-nums">{jod(row.shelf_price_jod)}</td>
                <td className="whitespace-nowrap py-2 text-end tabular-nums text-text-gray">{date(row.last_updated)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
