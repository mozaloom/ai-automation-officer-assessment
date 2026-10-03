"use client";

import { useState } from "react";
import type { PosRecord } from "@/lib/api/types";
import { aggregate, GROUPS, MEASURES, type GroupBy, type Measure } from "@/lib/chart";
import { STATUS_COLORS } from "@/lib/format";
import { useI18n } from "@/lib/i18n/I18nProvider";
import type { StockStatus } from "@/lib/api/types";

const LIMIT = 15;

/** A chart built from the records themselves: pick what to group by and what to measure. Bars flip in Arabic and every value is written out. */
export default function RecordsChart({ records }: { records: PosRecord[] }) {
  const { t, label, number, jod } = useI18n();
  const r = t.records;
  const [by, setBy] = useState<GroupBy>(new Set(records.map((x) => x.city)).size > 1 ? "city" : "store_name");
  const [measure, setMeasure] = useState<Measure>("count");
  const rows = aggregate(records, by, measure).slice(0, LIMIT);
  const max = Math.max(...rows.map((x) => x.value), 0.01);
  const format = (v: number) => (measure === "avgPrice" || measure === "minPrice" ? jod(v) : number(v));
  const nameOf = (key: string) => (by === "availability_status" ? t.status[key as StockStatus] : label(by === "store_name" ? "store_name" : by === "product_name" ? "product_name" : by, key));
  const select = "h-8 rounded-md border border-[#d0d5dd] bg-white px-2 text-sm text-text-dark focus-visible:border-brand-blue focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-blue/15";
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-text-gray">{r.groupBy}
          <select value={by} onChange={(e) => setBy(e.target.value as GroupBy)} className={select}>{GROUPS.map((g) => <option key={g} value={g}>{r.groups[g]}</option>)}</select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-text-gray">{r.measure}
          <select value={measure} onChange={(e) => setMeasure(e.target.value as Measure)} className={select}>{MEASURES.map((m) => <option key={m} value={m}>{r.measures[m]}</option>)}</select>
        </label>
      </div>
      {rows.length === 0 ? <p className="py-6 text-sm text-text-gray">{r.noChartData}</p> : (
        <ul aria-label={r.chartAria(r.measures[measure], r.groups[by])} className="space-y-1">
          {rows.map((row) => (
            <li key={row.key} className="grid grid-cols-[minmax(6rem,11rem)_1fr_auto] items-center gap-3 rounded-md px-2 py-1 text-sm transition-colors hover:bg-wash" title={`${nameOf(row.key)}: ${format(row.value)}`}>
              <span className="truncate text-text-dark">{nameOf(row.key)}</span>
              <span className="flex h-2.5"><span className="block h-full rounded-full" style={{ width: `${Math.max((row.value / max) * 100, 1.5)}%`, background: by === "availability_status" ? STATUS_COLORS[row.key as StockStatus] : "var(--color-brand-blue)" }} /></span>
              <span className="min-w-12 text-end tabular-nums text-text-dark">{format(row.value)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
