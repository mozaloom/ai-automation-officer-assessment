"use client";

import SortHeader from "@/components/ui/SortHeader";
import TableSearch from "@/components/ui/TableSearch";
import type { DashboardData } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/I18nProvider";
import { useTable } from "@/lib/table";

function Rate({ value }: { value: number }) {
  const { pct } = useI18n();
  const tone = value >= 40 ? "bg-stock-out" : value >= 25 ? "bg-stock-low" : "bg-stock-in";
  return (
    <span className="inline-flex items-center justify-end gap-2 tabular-nums">
      <span className="h-1.5 w-12 overflow-hidden rounded-full bg-wash" aria-hidden="true"><span className={`block h-full ${tone}`} style={{ width: `${Math.min(value, 100)}%` }} /></span>
      <span className="w-10 text-end text-text-dark">{pct(value)}</span>
    </span>
  );
}

/** A name that opens that row's records. */
function DrillName({ name, onClick }: { name: string; onClick: () => void }) {
  const { t } = useI18n();
  return (
    <button type="button" onClick={onClick} title={t.dashboard.interactive.openRecordsFor(name)} aria-label={t.dashboard.interactive.openRecordsFor(name)}
      className="max-w-full truncate text-start font-medium text-text-dark underline-offset-4 transition-colors hover:text-brand-blue hover:underline">{name}</button>
  );
}

export interface DrillTarget { product?: string; store?: string; title: string }

export function WatchProducts({ rows, onDrill }: { rows: DashboardData["at_risk_products"]; onDrill?: (target: DrillTarget) => void }) {
  const { t, locale, label, number } = useI18n();
  const table = useTable(rows, { product: (r) => label("product_name", r.product_name), category: (r) => label("category", r.category), low: (r) => r.low_stock, out: (r) => r.out_of_stock, rate: (r) => r.at_risk_pct },
    (r) => `${r.product_name} ${label("product_name", r.product_name)} ${label("category", r.category)}`, locale);
  if (!rows.length) return <p className="py-8 text-sm text-text-gray">{t.dashboard.nothingAtRisk}</p>;
  const w = t.dashboard.watchProducts;
  const h = (key: string, text: string, align: "start" | "end" = "start", cls = "") => <SortHeader label={text} active={table.sortKey === key} dir={table.dir} onSort={() => table.toggle(key)} align={align} className={cls} />;
  return (
    <div>
      <div className="mb-2"><TableSearch value={table.query} onChange={table.setQuery} /></div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-line">{h("product", w.product)}{h("category", w.category, "start", "hidden sm:table-cell")}{h("low", w.low, "end")}{h("out", w.out, "end")}{h("rate", w.rate, "end")}</tr></thead>
          <tbody className="divide-y divide-line">
            {table.rows.map((r) => (
              <tr key={r.product_name} className="transition-colors hover:bg-wash">
                <td className="max-w-[13rem] py-2.5 pe-3">{onDrill ? <DrillName name={label("product_name", r.product_name)} onClick={() => onDrill({ product: r.product_name, title: label("product_name", r.product_name) })} /> : label("product_name", r.product_name)}</td>
                <td className="hidden py-2.5 pe-3 text-text-gray sm:table-cell">{label("category", r.category)}</td>
                <td className="py-2.5 text-end tabular-nums">{number(r.low_stock)}</td>
                <td className="py-2.5 text-end tabular-nums">{number(r.out_of_stock)}</td>
                <td className="py-2.5 ps-3 text-end"><Rate value={r.at_risk_pct} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        {table.rows.length === 0 && <p className="py-6 text-center text-sm text-text-gray">{t.common.noRows}</p>}
      </div>
    </div>
  );
}

export function WatchStores({ rows, onDrill }: { rows: DashboardData["at_risk_stores"]; onDrill?: (target: DrillTarget) => void }) {
  const { t, locale, label, number } = useI18n();
  const table = useTable(rows, { store: (r) => label("store_name", r.store_name), city: (r) => label("city", r.city), low: (r) => r.low_stock, out: (r) => r.out_of_stock, listings: (r) => r.listings },
    (r) => `${r.store_name} ${label("store_name", r.store_name)} ${label("city", r.city)}`, locale);
  if (!rows.length) return <p className="py-8 text-sm text-text-gray">{t.dashboard.nothingAtRisk}</p>;
  const w = t.dashboard.watchStores;
  const h = (key: string, text: string, align: "start" | "end" = "start", cls = "") => <SortHeader label={text} active={table.sortKey === key} dir={table.dir} onSort={() => table.toggle(key)} align={align} className={cls} />;
  return (
    <div>
      <div className="mb-2"><TableSearch value={table.query} onChange={table.setQuery} /></div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-line">{h("store", w.store)}{h("city", w.city, "start", "hidden sm:table-cell")}{h("low", w.low, "end")}{h("out", w.out, "end")}{h("listings", w.listings, "end")}</tr></thead>
          <tbody className="divide-y divide-line">
            {table.rows.map((r) => (
              <tr key={r.store_name} className="transition-colors hover:bg-wash">
                <td className="max-w-[14rem] py-2.5 pe-3">{onDrill ? <DrillName name={label("store_name", r.store_name)} onClick={() => onDrill({ store: r.store_name, title: label("store_name", r.store_name) })} /> : label("store_name", r.store_name)}</td>
                <td className="hidden py-2.5 pe-3 text-text-gray sm:table-cell">{label("city", r.city)}</td>
                <td className="py-2.5 text-end tabular-nums">{number(r.low_stock)}</td>
                <td className="py-2.5 text-end tabular-nums">{number(r.out_of_stock)}</td>
                <td className="py-2.5 text-end tabular-nums text-text-gray">{number(r.listings)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {table.rows.length === 0 && <p className="py-6 text-center text-sm text-text-gray">{t.common.noRows}</p>}
      </div>
    </div>
  );
}
