"use client";

import { Bar, BarChart, CartesianGrid, Cell, Tooltip, XAxis, YAxis } from "recharts";
import { SEGMENT_COLOR } from "@/lib/segments";

// Fixed dimensions rather than ResponsiveContainer: this dashboard's two-column
// grid has a known width range, and ResponsiveContainer's ResizeObserver-based
// measurement is unreliable on first mount in some browser/automation contexts
// -- a fixed size is worth the small loss of fluid responsiveness here.
export default function SegmentBarChart({ data }: { data: { segment: string; count: number }[] }) {
  return (
    <BarChart width={500} height={240} data={data} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
      <CartesianGrid strokeDasharray="3 3" stroke="#e3e6eb" horizontal={false} />
      <XAxis type="number" tick={{ fontSize: 12, fill: "#667085" }} axisLine={false} tickLine={false} />
      <YAxis
        type="category"
        dataKey="segment"
        width={116}
        tick={{ fontSize: 12.5, fill: "#101828" }}
        axisLine={false}
        tickLine={false}
      />
      <Tooltip
        cursor={{ fill: "rgba(16,24,40,0.04)" }}
        contentStyle={{
          borderRadius: 8,
          border: "1px solid #e3e6eb",
          fontSize: 12.5,
          boxShadow: "0 4px 12px rgba(16,24,40,0.08)",
        }}
      />
      <Bar dataKey="count" name="Customers" radius={[0, 5, 5, 0]} barSize={26}>
        {data.map((entry) => (
          <Cell key={entry.segment} fill={SEGMENT_COLOR[entry.segment] ?? "#2b5fd9"} />
        ))}
      </Bar>
    </BarChart>
  );
}
