"use client";

import { Bar, BarChart, CartesianGrid, Cell, Tooltip, XAxis, YAxis } from "recharts";
import { riskBand } from "@/lib/risk";
import type { ChurnByDimension } from "@/lib/types";

// Fixed dimensions -- see SegmentBarChart.tsx for why this doesn't use ResponsiveContainer.
export default function ChurnByDimensionChart({ data }: { data: ChurnByDimension[] }) {
  const sorted = [...data]
    .sort((a, b) => b.mean_churn_probability - a.mean_churn_probability)
    .map((row) => ({ ...row, label: row.value.replaceAll("_", " ") }));
  return (
    <BarChart width={500} height={240} data={sorted} margin={{ left: 0, right: 12, top: 8, bottom: 4 }}>
      <CartesianGrid strokeDasharray="3 3" stroke="#e3e6eb" vertical={false} />
      <XAxis dataKey="label" tick={{ fontSize: 12, fill: "#101828" }} axisLine={false} tickLine={false} />
      <YAxis
        tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
        tick={{ fontSize: 12, fill: "#667085" }}
        axisLine={false}
        tickLine={false}
        domain={[0, 1]}
      />
      <Tooltip
        formatter={(value: number) => `${(value * 100).toFixed(1)}%`}
        cursor={{ fill: "rgba(16,24,40,0.04)" }}
        contentStyle={{
          borderRadius: 8,
          border: "1px solid #e3e6eb",
          fontSize: 12.5,
          boxShadow: "0 4px 12px rgba(16,24,40,0.08)",
        }}
      />
      <Bar dataKey="mean_churn_probability" name="Mean churn probability" radius={[5, 5, 0, 0]} maxBarSize={44}>
        {sorted.map((row) => (
          <Cell key={row.value} fill={riskBand(row.mean_churn_probability).color} />
        ))}
      </Bar>
    </BarChart>
  );
}
