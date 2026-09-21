import Link from "next/link";
import { listSegments } from "@/lib/api";
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format";

const SEGMENT_TONE: Record<string, string> = {
  Champions: "text-retain",
  "Steady Regulars": "text-accent",
  "New / Developing": "text-value",
  "Dormant / Lost": "text-risk",
};

export default async function SegmentsPage() {
  const segments = await listSegments();
  const sorted = [...segments].sort((a, b) => b.mean_predicted_clv - a.mean_predicted_clv);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-medium">Segments</h1>
        <p className="mt-1 text-sm text-ink-soft">
          K-Means (k=4), profiled and named from behavior — see docs/segmentation_report.md.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        {sorted.map((segment) => (
          <Link
            key={segment.segment}
            href={`/segments/${encodeURIComponent(segment.segment)}`}
            className="flex flex-col gap-3 rounded border border-line bg-surface p-5 hover:border-accent"
          >
            <div className={`text-lg font-medium ${SEGMENT_TONE[segment.segment] ?? "text-ink"}`}>{segment.segment}</div>
            <div className="tabular text-sm text-ink-soft">{formatNumber(segment.size)} customers</div>
            <div className="flex gap-6 text-sm">
              <div>
                <div className="text-ink-soft">Mean churn</div>
                <div className="tabular">{formatPercent(segment.mean_churn_probability)}</div>
              </div>
              <div>
                <div className="text-ink-soft">Mean CLV</div>
                <div className="tabular">{formatCurrency(segment.mean_predicted_clv)}</div>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
