"use client";

import dynamic from "next/dynamic";

// Recharts measures Y-axis tick label wrapping with a canvas that only
// exists in the browser, so its SSR output for a long label like "Steady
// Regulars" differs from what the client renders -- a genuine hydration
// mismatch (confirmed via the dev overlay), not just a lint nit. Loading
// this client-only sidesteps it: there's nothing to mismatch if the chart
// never renders on the server. The placeholder matches the chart's fixed
// dimensions (see SegmentBarChartImpl.tsx) so there's no layout shift.
const SegmentBarChart = dynamic(() => import("./SegmentBarChartImpl"), {
  ssr: false,
  loading: () => <div style={{ width: 500, height: 240 }} />,
});

export default SegmentBarChart;
