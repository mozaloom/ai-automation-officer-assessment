"use client";

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { STATUS_COLORS } from "@/lib/format";

export interface StackRow { name: string; in_stock: number; low_stock: number; out_of_stock: number }

interface Props {
  data: StackRow[];
  /** "horizontal" draws bars left to right (good for long names); "vertical" draws columns. */
  orientation?: "horizontal" | "vertical";
  height?: number;
  label: string;
}

const SERIES = [
  { key: "in_stock", name: "In Stock", color: STATUS_COLORS["In Stock"] },
  { key: "low_stock", name: "Low Stock", color: STATUS_COLORS["Low Stock"] },
  { key: "out_of_stock", name: "Out of Stock", color: STATUS_COLORS["Out of Stock"] },
] as const;

const tick = { fontSize: 11, fill: "var(--color-text-gray)" };

export default function StackedBars({ data, orientation = "vertical", height = 280, label }: Props) {
  const reduceMotion = useReducedMotion(); // hooks first: before any early return
  if (!data.length) return <div className="py-16 text-center text-sm text-text-gray">No listings match these filters.</div>;
  const horizontal = orientation === "horizontal";
  return (
    <div style={{ height }} className="w-full" role="img" aria-label={label}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout={horizontal ? "vertical" : "horizontal"} margin={{ top: 8, right: 8, bottom: 0, left: horizontal ? 8 : -16 }}>
          <CartesianGrid stroke="rgba(0,0,0,0.06)" strokeDasharray="3 3" vertical={horizontal} horizontal={!horizontal} />
          {/* Recharts only sees direct children, so no fragments around the axes. */}
          {horizontal && <XAxis type="number" tick={tick} tickLine={false} axisLine={false} allowDecimals={false} />}
          {horizontal && <YAxis type="category" dataKey="name" width={96} tick={tick} tickLine={false} axisLine={false} />}
          {!horizontal && <XAxis dataKey="name" tick={tick} tickLine={false} axisLine={false} interval={0} angle={-30} textAnchor="end" height={52} />}
          {!horizontal && <YAxis tick={tick} tickLine={false} axisLine={false} allowDecimals={false} />}
          <Tooltip cursor={{ fill: "rgba(108,72,197,0.06)" }} contentStyle={{ borderRadius: 12, border: "1px solid rgba(0,0,0,0.08)", fontSize: 12, boxShadow: "0 4px 16px rgba(18,48,174,0.08)" }} labelStyle={{ fontWeight: 600, color: "var(--color-text-dark)" }} />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
          {SERIES.map((s, i) => (
            <Bar key={s.key} isAnimationActive={!reduceMotion} animationDuration={500} dataKey={s.key} name={s.name} stackId="stock" fill={s.color} maxBarSize={horizontal ? 22 : 34} radius={i === SERIES.length - 1 ? (horizontal ? [0, 6, 6, 0] : [6, 6, 0, 0]) : 0} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
