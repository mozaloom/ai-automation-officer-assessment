"use client";

import { STATUS_COLORS, STATUS_KEYS } from "@/lib/format";
import { useI18n } from "@/lib/i18n/I18nProvider";

export interface StateRow { value: string; name: string; in_stock: number; low_stock: number; out_of_stock: number }

const SEGMENTS = [
  { key: "in_stock", status: STATUS_KEYS[0] },
  { key: "low_stock", status: STATUS_KEYS[1] },
  { key: "out_of_stock", status: STATUS_KEYS[2] },
] as const;

interface Props { rows: StateRow[]; selected?: string; onSelect?: (value: string) => void }

/** Ranked horizontal bars, split by state. Rows are buttons: clicking one filters the dashboard to it; hovering a segment gives exact numbers. */
export default function StateBars({ rows, selected, onSelect }: Props) {
  const { t, number, pct } = useI18n();
  if (!rows.length) return <p className="py-8 text-sm text-text-gray">{t.dashboard.noListings}</p>;
  const ranked = rows.map((r) => ({ ...r, total: r.in_stock + r.low_stock + r.out_of_stock })).sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));
  const max = Math.max(...ranked.map((r) => r.total), 1);
  return (
    <div>
      <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-gray" aria-hidden="true">
        {STATUS_KEYS.map((status) => <li key={status} className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: STATUS_COLORS[status] }} />{t.status[status]}</li>)}
      </ul>
      <ul className="space-y-0.5">
        {ranked.map((row) => {
          const dim = selected && selected !== row.value;
          const summary = `${row.name}: ${SEGMENTS.map((s) => `${t.status[s.status]} ${number(row[s.key])}`).join(", ")}`;
          const inner = (
            <>
              <span className="truncate text-start text-text-dark" title={row.name}>{row.name}</span>
              <span className="flex h-2.5 overflow-hidden rounded-full bg-wash" style={{ width: `${(row.total / max) * 100}%`, minWidth: "0.5rem" }}>
                {SEGMENTS.map((s) => row[s.key] > 0 && (
                  <span key={s.key} title={t.dashboard.interactive.segment(t.status[s.status], number(row[s.key]), pct((row[s.key] / row.total) * 100))}
                    style={{ width: `${(row[s.key] / row.total) * 100}%`, background: STATUS_COLORS[s.status] }} className="transition-opacity hover:opacity-70" />
                ))}
              </span>
              <span className="w-10 text-end tabular-nums text-text-gray">{number(row.total)}</span>
            </>
          );
          const cls = `grid w-full grid-cols-[minmax(6rem,9rem)_1fr_auto] items-center gap-3 rounded-md px-2 py-1 text-sm transition-colors ${dim ? "opacity-45" : ""}`;
          return (
            <li key={row.value} aria-label={summary}>
              {onSelect ? (
                <button type="button" onClick={() => onSelect(row.value)} aria-pressed={selected === row.value} className={`${cls} hover:bg-wash ${selected === row.value ? "bg-brand-blue/[0.06] ring-1 ring-brand-blue/30" : ""}`}>{inner}</button>
              ) : <div className={cls}>{inner}</div>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
