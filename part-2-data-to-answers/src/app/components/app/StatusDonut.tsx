"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { STATUS_COLORS, formatNumber, formatPct } from "@/lib/format";
import type { DashboardData } from "@/lib/api/types";

export default function StatusDonut({ data }: { data: DashboardData["status_split"] }) {
  const reduceMotion = useReducedMotion();
  const total = data.reduce((sum, s) => sum + s.count, 0);
  if (total === 0) return <div className="py-16 text-center text-sm text-text-gray">No listings match these filters.</div>;
  return (
    <div>
      <div className="relative h-56" role="img" aria-label={`Stock status split of ${formatNumber(total)} listings`}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie isAnimationActive={!reduceMotion} animationDuration={500} data={data} innerRadius={62} outerRadius={92} paddingAngle={2} dataKey="count" nameKey="status" stroke="none">
              {data.map((s) => <Cell key={s.status} fill={STATUS_COLORS[s.status]} />)}
            </Pie>
            <Tooltip formatter={(value, name) => [formatNumber(Number(value)), String(name)]} contentStyle={{ borderRadius: 12, border: "1px solid rgb(229 231 235)", boxShadow: "0 8px 32px 0 rgb(18 48 174 / 0.18)" }} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold text-text-dark">{formatNumber(total)}</span>
          <span className="text-xs text-text-gray">listings</span>
        </div>
      </div>
      <ul className="mt-2 space-y-1.5">
        {data.map((s) => (
          <li key={s.status} className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 text-text-dark"><span className="h-2.5 w-2.5 rounded-full" style={{ background: STATUS_COLORS[s.status] }} aria-hidden="true" />{s.status}</span>
            <span className="tabular-nums text-text-gray">{formatNumber(s.count)} <span className="text-xs">({formatPct(s.pct)})</span></span>
          </li>
        ))}
      </ul>
    </div>
  );
}
