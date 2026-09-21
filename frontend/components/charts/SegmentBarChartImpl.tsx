"use client";

import { Bar, BarChart, CartesianGrid, Cell, Tooltip, XAxis, YAxis } from "recharts";

const SEGMENT_COLOR: Record<string, string> = {
  Champions: "#29694f",
  "Steady Regulars": "#1d3557",
  "New / Developing": "#9c7a22",
  "Dormant / Lost": "#b0402a",
};

// Fixed dimensions rather than ResponsiveContainer: this dashboard's two-column
// grid has a known width range, and ResponsiveContainer's ResizeObserver-based
// measurement is unreliable on first mount in some browser/automation contexts
// -- a fixed size is worth the small loss of fluid responsiveness here.
export default function SegmentBarChart({ data }: { data: { segment: string; count: number }[] }) {
  return (
    <BarChart width={480} height={220} data={data} layout="vertical" margin={{ left: 24, right: 16, top: 8, bottom: 8 }}>
      <CartesianGrid strokeDasharray="3 3" stroke="#d8ddd9" horizontal={false} />
      <XAxis type="number" tick={{ fontSize: 12, fill: "#4b5563" }} axisLine={false} tickLine={false} />
      <YAxis type="category" dataKey="segment" width={120} tick={{ fontSize: 12, fill: "#14181f" }} axisLine={false} tickLine={false} />
      <Tooltip cursor={{ fill: "rgba(20,24,31,0.04)" }} contentStyle={{ borderRadius: 4, borderColor: "#d8ddd9", fontSize: 12 }} />
      <Bar dataKey="count" radius={[0, 3, 3, 0]}>
        {data.map((entry) => (
          <Cell key={entry.segment} fill={SEGMENT_COLOR[entry.segment] ?? "#1d3557"} />
        ))}
      </Bar>
    </BarChart>
  );
}
