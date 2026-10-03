"use client";

import { STATUS_COLORS, STATUS_KEYS } from "@/lib/format";
import { useI18n } from "@/lib/i18n/I18nProvider";

export interface StateRow { name: string; in_stock: number; low_stock: number; out_of_stock: number }

const SEGMENTS = [
  { key: "in_stock", status: STATUS_KEYS[0] },
  { key: "low_stock", status: STATUS_KEYS[1] },
  { key: "out_of_stock", status: STATUS_KEYS[2] },
] as const;

/** Ranked horizontal bars: one row per city or category, split by state, with the total written at the end of the row. */
export default function StateBars({ rows }: { rows: StateRow[] }) {
  const { t, number } = useI18n();
  if (!rows.length) return <p className="py-8 text-sm text-text-gray">{t.dashboard.noListings}</p>;
  const ranked = rows.map((r) => ({ ...r, total: r.in_stock + r.low_stock + r.out_of_stock })).sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));
  const max = Math.max(...ranked.map((r) => r.total), 1);
  return (
    <div>
      <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-gray" aria-hidden="true">
        {STATUS_KEYS.map((status) => <li key={status} className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: STATUS_COLORS[status] }} />{t.status[status]}</li>)}
      </ul>
      <ul className="space-y-2">
        {ranked.map((row) => (
          <li key={row.name} className="grid grid-cols-[minmax(6rem,9rem)_1fr_auto] items-center gap-3 text-sm"
            aria-label={`${row.name}: ${SEGMENTS.map((s) => `${t.status[s.status]} ${number(row[s.key])}`).join(", ")}`}>
            <span className="truncate text-text-dark" title={row.name}>{row.name}</span>
            <span className="flex h-2.5 overflow-hidden rounded-full bg-wash" style={{ width: `${(row.total / max) * 100}%`, minWidth: "0.5rem" }}>
              {SEGMENTS.map((s) => row[s.key] > 0 && <span key={s.key} style={{ width: `${(row[s.key] / row.total) * 100}%`, background: STATUS_COLORS[s.status] }} />)}
            </span>
            <span className="w-10 text-end tabular-nums text-text-gray">{number(row.total)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
