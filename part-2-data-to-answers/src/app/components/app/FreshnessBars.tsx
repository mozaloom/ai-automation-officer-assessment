"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { formatShortDate } from "@/lib/format";
import type { DashboardData } from "@/lib/api/types";

const tick = { fontSize: 11, fill: "var(--color-text-gray)" };

export default function FreshnessBars({ data }: { data: DashboardData["freshness"] }) {
  const reduceMotion = useReducedMotion();
  if (!data.length) return <div className="py-12 text-center text-sm text-text-gray">No records.</div>;
  const rows = data.map((d) => ({ label: formatShortDate(d.date), count: d.count }));
  return (
    <div className="h-48 w-full" role="img" aria-label="Listings by last updated date">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid stroke="rgba(0,0,0,0.06)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" tick={tick} tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={16} />
          <YAxis tick={tick} tickLine={false} axisLine={false} allowDecimals={false} />
          <Tooltip cursor={{ fill: "rgba(108,72,197,0.06)" }} formatter={(value) => [String(value), "Listings"]} contentStyle={{ borderRadius: 12, fontSize: 12 }} />
          <Bar isAnimationActive={!reduceMotion} animationDuration={500} dataKey="count" name="Listings" fill="var(--color-brand-blue)" radius={[6, 6, 0, 0]} maxBarSize={22} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
