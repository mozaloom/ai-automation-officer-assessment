"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import FullScreen from "@/components/ui/FullScreen";
import SortHeader from "@/components/ui/SortHeader";
import TableSearch from "@/components/ui/TableSearch";
import type { PosRecord } from "@/lib/api/types";
import { STATUS_KEYS } from "@/lib/format";
import { useI18n } from "@/lib/i18n/I18nProvider";
import { useTable } from "@/lib/table";
import RecordsChart from "./RecordsChart";
import StatusBadge from "./StatusBadge";

const MAX_ROWS = 25;
const SEARCH_FROM = 8; // a search box only helps once there are enough rows to search

interface Props { records: PosRecord[]; total: number; asOf: string; defaultOpen?: boolean; inDialog?: boolean; collapsible?: boolean; limit?: number; defaultView?: "table" | "chart" }

/** The records an answer was built from: collapsible, sortable, searchable, and viewable full screen. */
export default function RecordsTable({ records, total, asOf, defaultOpen = true, inDialog = false, collapsible = true, limit = MAX_ROWS, defaultView = "table" }: Props) {
  const [view, setView] = useState<"table" | "chart">(defaultView);
  const { t, locale, label, pack, jod, date, number } = useI18n();
  const r = t.records;
  const base = records.slice(0, limit);
  const table = useTable(
    base,
    {
      store: (x) => label("store_name", x.store_name),
      location: (x) => `${label("area", x.area)} ${label("city", x.city)}`,
      product: (x) => label("product_name", x.product_name),
      state: (x) => STATUS_KEYS.indexOf(x.availability_status),
      quantity: (x) => x.quantity_on_shelf,
      price: (x) => x.shelf_price_jod,
      updated: (x) => x.last_updated,
    },
    (x) => [x.store_name, x.area, x.city, x.product_name, label("store_name", x.store_name), label("area", x.area), label("city", x.city), label("product_name", x.product_name)].join(" "),
    locale,
  );
  if (!records.length) return null;
  const head = (key: string, text: string, align: "start" | "end" = "start", extra = "") => (
    <SortHeader label={text} active={table.sortKey === key} dir={table.dir} onSort={() => table.toggle(key)} align={align} className={`pe-3 ${extra}`} />
  );
  const body = (
    <>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <div role="group" aria-label={r.title} className="inline-flex overflow-hidden rounded-md border border-[#d0d5dd] text-sm">
            {(["table", "chart"] as const).map((v) => (
              <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)} className={`h-8 px-3 transition-colors ${view === v ? "bg-brand-blue text-white" : "bg-white text-text-dark hover:bg-wash"}`}>{v === "table" ? r.viewTable : r.viewChart}</button>
            ))}
          </div>
          {view === "table" && base.length > SEARCH_FROM && <TableSearch value={table.query} onChange={table.setQuery} />}
        </div>
        {!inDialog && (
          <FullScreen title={r.title}>
            <RecordsTable records={records} total={total} asOf={asOf} inDialog collapsible={false} limit={records.length} defaultView={view} />
          </FullScreen>
        )}
      </div>
      {view === "chart" ? <RecordsChart records={base} /> : <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-line">
              {head("store", r.store)}{head("location", r.location)}{head("product", r.product)}{head("state", r.state)}{head("quantity", r.quantity, "end")}{head("price", r.price, "end")}{head("updated", r.updated, "end", "pe-0")}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {table.rows.map((row) => (
              <tr key={`${row.store_name}|${row.product_name}|${row.pack_size}`} className="transition-colors hover:bg-wash">
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
        {table.rows.length === 0 && <p className="py-6 text-center text-sm text-text-gray">{t.common.noRows}</p>}
      </div>}
    </>
  );
  if (!collapsible) {
    return (
      <div data-testid="records">
        <p className="mb-3 text-xs text-text-gray">{r.showing(base.length, total, date(asOf))}</p>
        {body}
      </div>
    );
  }
  return (
    <details open={defaultOpen} className="group enter mt-4 border-t border-line pt-3" data-testid="records">
      <summary className="mb-2 flex cursor-pointer list-none flex-wrap items-center justify-between gap-x-4 gap-y-1 rounded-md [&::-webkit-details-marker]:hidden">
        <span className="flex items-center gap-1.5 text-sm font-semibold text-text-dark">
          <ChevronDown className="h-4 w-4 text-text-gray transition-transform duration-150 group-open:rotate-180" aria-hidden="true" />{r.title}
        </span>
        <span className="text-xs text-text-gray">{r.showing(base.length, total, date(asOf))}</span>
      </summary>
      {body}
    </details>
  );
}
