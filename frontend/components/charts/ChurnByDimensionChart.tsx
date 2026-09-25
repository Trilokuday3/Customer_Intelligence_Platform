"use client";

import dynamic from "next/dynamic";

// See SegmentBarChart.tsx for why this is loaded client-only: Recharts'
// SSR tick-label measurement (no canvas in Node) can disagree with the
// client's, which is a real hydration mismatch, not a stylistic choice.
const ChurnByDimensionChart = dynamic(() => import("./ChurnByDimensionChartImpl"), {
  ssr: false,
  loading: () => <div style={{ width: 500, height: 240 }} />,
});

export default ChurnByDimensionChart;
