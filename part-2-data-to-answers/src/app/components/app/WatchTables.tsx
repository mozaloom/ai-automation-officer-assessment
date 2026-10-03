"use client";

import type { DashboardData } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

const head = "py-2 text-xs font-medium text-text-gray";

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

export function WatchProducts({ rows }: { rows: DashboardData["at_risk_products"] }) {
  const { t, label, number } = useI18n();
  if (!rows.length) return <p className="py-8 text-sm text-text-gray">{t.dashboard.nothingAtRisk}</p>;
  const w = t.dashboard.watchProducts;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead><tr className="border-b border-line"><th className={`${head} text-start`}>{w.product}</th><th className={`${head} hidden text-start sm:table-cell`}>{w.category}</th><th className={`${head} text-end`}>{w.low}</th><th className={`${head} text-end`}>{w.out}</th><th className={`${head} text-end`}>{w.rate}</th></tr></thead>
        <tbody className="divide-y divide-line">
          {rows.map((r) => (
            <tr key={r.product_name}>
              <td className="max-w-[13rem] truncate py-2.5 pe-3 font-medium text-text-dark">{label("product_name", r.product_name)}</td>
              <td className="hidden py-2.5 pe-3 text-text-gray sm:table-cell">{label("category", r.category)}</td>
              <td className="py-2.5 text-end tabular-nums">{number(r.low_stock)}</td>
              <td className="py-2.5 text-end tabular-nums">{number(r.out_of_stock)}</td>
              <td className="py-2.5 ps-3 text-end"><Rate value={r.at_risk_pct} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function WatchStores({ rows }: { rows: DashboardData["at_risk_stores"] }) {
  const { t, label, number } = useI18n();
  if (!rows.length) return <p className="py-8 text-sm text-text-gray">{t.dashboard.nothingAtRisk}</p>;
  const w = t.dashboard.watchStores;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead><tr className="border-b border-line"><th className={`${head} text-start`}>{w.store}</th><th className={`${head} hidden text-start sm:table-cell`}>{w.city}</th><th className={`${head} text-end`}>{w.low}</th><th className={`${head} text-end`}>{w.out}</th><th className={`${head} text-end`}>{w.listings}</th></tr></thead>
        <tbody className="divide-y divide-line">
          {rows.map((r) => (
            <tr key={r.store_name}>
              <td className="max-w-[14rem] truncate py-2.5 pe-3 font-medium text-text-dark">{label("store_name", r.store_name)}</td>
              <td className="hidden py-2.5 pe-3 text-text-gray sm:table-cell">{label("city", r.city)}</td>
              <td className="py-2.5 text-end tabular-nums">{number(r.low_stock)}</td>
              <td className="py-2.5 text-end tabular-nums">{number(r.out_of_stock)}</td>
              <td className="py-2.5 text-end tabular-nums text-text-gray">{number(r.listings)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
