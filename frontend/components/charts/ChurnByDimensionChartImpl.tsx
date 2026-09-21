"use client";

import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";
import type { ChurnByDimension } from "@/lib/types";

// Fixed dimensions -- see SegmentBarChart.tsx for why this doesn't use ResponsiveContainer.
export default function ChurnByDimensionChart({ data }: { data: ChurnByDimension[] }) {
  const sorted = [...data].sort((a, b) => b.mean_churn_probability - a.mean_churn_probability);
  return (
    <BarChart width={480} height={220} data={sorted} margin={{ left: 0, right: 16, top: 8, bottom: 8 }}>
      <CartesianGrid strokeDasharray="3 3" stroke="#d8ddd9" vertical={false} />
      <XAxis dataKey="value" tick={{ fontSize: 12, fill: "#14181f" }} axisLine={false} tickLine={false} />
      <YAxis
        tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
        tick={{ fontSize: 12, fill: "#4b5563" }}
        axisLine={false}
        tickLine={false}
      />
      <Tooltip
        formatter={(value: number) => `${(value * 100).toFixed(1)}%`}
        cursor={{ fill: "rgba(20,24,31,0.04)" }}
        contentStyle={{ borderRadius: 4, borderColor: "#d8ddd9", fontSize: 12 }}
      />
      <Bar dataKey="mean_churn_probability" fill="#b0402a" radius={[3, 3, 0, 0]} />
    </BarChart>
  );
}
