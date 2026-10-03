"use client";

import { STATUS_COLORS, STATUS_KEYS } from "@/lib/format";
import type { DashboardData } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

/** One 100 % bar for the whole data set, with the numbers written out beneath it. */
export default function StockShareBar({ data }: { data: DashboardData["status_split"] }) {
  const { t, number, pct } = useI18n();
  const total = data.reduce((sum, s) => sum + s.count, 0);
  if (total === 0) return <p className="py-8 text-sm text-text-gray">{t.dashboard.noListings}</p>;
  const rows = STATUS_KEYS.map((status) => data.find((s) => s.status === status) ?? { status, count: 0, pct: 0 });
  return (
    <div>
      <div role="img" aria-label={t.dashboard.share.aria(number(total))} className="flex h-3 w-full overflow-hidden rounded-full bg-wash">
        {rows.map((s) => <div key={s.status} style={{ width: `${s.pct}%`, background: STATUS_COLORS[s.status] }} />)}
      </div>
      <ul className="mt-4 grid gap-2 sm:grid-cols-3">
        {rows.map((s) => (
          <li key={s.status} className="text-sm">
            <span className="flex items-center gap-2 text-text-gray"><span className="h-2 w-2 rounded-full" style={{ background: STATUS_COLORS[s.status] }} aria-hidden="true" />{t.status[s.status]}</span>
            <span className="mt-0.5 block tabular-nums text-text-dark"><span className="text-lg font-semibold">{number(s.count)}</span> <span className="text-xs text-text-gray">{pct(s.pct)}</span></span>
          </li>
        ))}
      </ul>
    </div>
  );
}
