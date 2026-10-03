"use client";

import { STATUS_COLORS, STATUS_KEYS } from "@/lib/format";
import type { DashboardData, StockStatus } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

interface Props { data: DashboardData["status_split"]; selected?: string; onSelect?: (status: StockStatus) => void }

/** One 100 % bar for the whole data set. Segments and legend entries filter the dashboard to that state when clicked. */
export default function StockShareBar({ data, selected, onSelect }: Props) {
  const { t, number, pct } = useI18n();
  const total = data.reduce((sum, s) => sum + s.count, 0);
  if (total === 0) return <p className="py-8 text-sm text-text-gray">{t.dashboard.noListings}</p>;
  const rows = STATUS_KEYS.map((status) => data.find((s) => s.status === status) ?? { status, count: 0, pct: 0 });
  return (
    <div>
      <div role="img" aria-label={t.dashboard.share.aria(number(total))} className="flex h-3 w-full overflow-hidden rounded-full bg-wash">
        {rows.map((s) => (
          <div key={s.status} title={t.dashboard.interactive.segment(t.status[s.status], number(s.count), pct(s.pct))}
            style={{ width: `${s.pct}%`, background: STATUS_COLORS[s.status], opacity: selected && selected !== s.status ? 0.35 : 1 }} className="transition-opacity hover:opacity-70" />
        ))}
      </div>
      <ul className="mt-3 grid gap-1 sm:grid-cols-3">
        {rows.map((s) => {
          const content = (
            <>
              <span className="flex items-center gap-2 text-text-gray"><span className="h-2 w-2 rounded-full" style={{ background: STATUS_COLORS[s.status] }} aria-hidden="true" />{t.status[s.status]}</span>
              <span className="mt-0.5 block tabular-nums text-text-dark"><span className="text-lg font-semibold">{number(s.count)}</span> <span className="text-xs text-text-gray">{pct(s.pct)}</span></span>
            </>
          );
          const cls = "block w-full rounded-md px-2 py-1.5 text-start text-sm transition-colors";
          return (
            <li key={s.status}>
              {onSelect ? <button type="button" onClick={() => onSelect(s.status)} aria-pressed={selected === s.status} className={`${cls} hover:bg-wash ${selected === s.status ? "bg-brand-blue/[0.06] ring-1 ring-brand-blue/30" : ""}`}>{content}</button> : <div className={cls}>{content}</div>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
