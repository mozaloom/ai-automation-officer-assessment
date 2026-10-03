"use client";

import type { DashboardData } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

/** One column per update date. Static: it shows how recent the data is, not a trend. */
export default function FreshnessStrip({ data }: { data: DashboardData["freshness"] }) {
  const { t, date, number } = useI18n();
  if (!data.length) return <p className="py-8 text-sm text-text-gray">{t.dashboard.noListings}</p>;
  const max = Math.max(...data.map((d) => d.count), 1);
  const labelled = (i: number, count: number) => data.length <= 7 || i === 0 || i === data.length - 1 || count === max; // crowded charts label only the ends and the peak
  return (
    <ul role="img" aria-label={t.dashboard.freshness.aria} className="flex h-32 items-end gap-2" dir="ltr">
      {data.map((d, i) => (
        <li key={d.date} className="flex h-full min-w-0 flex-1 flex-col justify-end text-center" title={`${date(d.date)}: ${number(d.count)} ${t.dashboard.listingsUnit}`}>
          <span className="text-xs tabular-nums text-text-gray">{number(d.count)}</span>
          <span className="mt-1 w-full rounded-t-sm bg-brand-blue" style={{ height: `${Math.max((d.count / max) * 70, 3)}%` }} />
          <span className={`mt-1.5 h-4 text-[11px] text-text-gray ${data.length > 7 ? "overflow-visible whitespace-nowrap" : "truncate"}`}>{labelled(i, d.count) ? date(d.date, "short") : ""}</span>
        </li>
      ))}
    </ul>
  );
}
