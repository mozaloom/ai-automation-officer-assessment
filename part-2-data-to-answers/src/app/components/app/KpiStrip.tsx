"use client";

import { STATUS_COLORS } from "@/lib/format";
import type { DashboardData } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

/** The headline numbers as one row separated by hairlines: no icons, no cards, no hover. */
export default function KpiStrip({ kpis }: { kpis: DashboardData["kpis"] }) {
  const { t, number, pct } = useI18n();
  const cells = [
    { id: "listings", label: t.dashboard.kpi.listings, value: kpis.listings, hint: t.dashboard.kpi.scope(kpis.stores, kpis.products, kpis.cities) },
    { id: "in-stock", label: t.dashboard.kpi.inStock, value: kpis.in_stock, hint: pct(kpis.in_stock_pct), dot: STATUS_COLORS["In Stock"] },
    { id: "low-stock", label: t.dashboard.kpi.lowStock, value: kpis.low_stock, hint: pct(kpis.low_stock_pct), dot: STATUS_COLORS["Low Stock"] },
    { id: "out-of-stock", label: t.dashboard.kpi.outOfStock, value: kpis.out_of_stock, hint: pct(kpis.out_of_stock_pct), dot: STATUS_COLORS["Out of Stock"] },
  ];
  return (
    <dl className="grid grid-cols-2 border-y border-line lg:grid-cols-4">
      {cells.map((cell, index) => (
        <div key={cell.id} className={`min-w-0 px-4 py-5 lg:py-6 ${index % 2 === 0 ? "ps-0" : "border-s border-line"} ${index > 1 ? "border-t border-line lg:border-t-0" : ""} ${index > 0 ? "lg:border-s lg:border-line lg:ps-6" : ""}`}>
          <dt className="flex items-center gap-2 text-sm text-text-gray">
            {cell.dot && <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: cell.dot }} aria-hidden="true" />}
            {cell.label}
          </dt>
          <dd className="mt-1.5 text-3xl font-semibold tabular-nums tracking-tight text-text-dark" data-testid={`kpi-${cell.id}`}>{number(cell.value)}</dd>
          <dd className="mt-1 truncate text-xs text-text-gray">{cell.hint}</dd>
        </div>
      ))}
    </dl>
  );
}
