import Link from "next/link";
import { listSegments } from "@/lib/api";
import { formatCurrency, formatNumber, formatPercent } from "@/lib/format";
import { riskBand } from "@/lib/risk";
import { SEGMENT_COLOR } from "@/lib/segments";
import PageHeader from "@/components/PageHeader";

export default async function SegmentsPage() {
  const segments = await listSegments();
  const sorted = [...segments].sort((a, b) => b.mean_predicted_clv - a.mean_predicted_clv);
  const total = sorted.reduce((sum, s) => sum + s.size, 0);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Segments"
        description="Customers grouped by how they actually buy (K-Means, k=4), then named from each group's profile. Open a segment to see who is most at risk."
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {sorted.map((segment) => {
          const color = SEGMENT_COLOR[segment.segment] ?? "#2b5fd9";
          const band = riskBand(segment.mean_churn_probability);
          return (
            <Link
              key={segment.segment}
              href={`/segments/${encodeURIComponent(segment.segment)}`}
              className="group flex flex-col gap-5 rounded-[10px] border border-line bg-surface p-5 transition-colors hover:border-line-strong"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="h-9 w-1.5 rounded-full" style={{ backgroundColor: color }} aria-hidden />
                  <div>
                    <div className="text-lg font-semibold tracking-tight">{segment.segment}</div>
                    <div className="tabular text-sm text-ink-soft">
                      {formatNumber(segment.size)} customers · {formatPercent(total ? segment.size / total : 0, 0)} of base
                    </div>
                  </div>
                </div>
                <span
                  className="rounded-full px-2.5 py-0.5 text-xs font-semibold"
                  style={{ backgroundColor: band.soft, color: band.color }}
                >
                  {band.label} risk
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4 border-t border-line pt-4">
                <div>
                  <div className="text-xs text-ink-soft">Mean churn probability</div>
                  <div className="tabular mt-0.5 text-xl font-semibold" style={{ color: band.color }}>
                    {formatPercent(segment.mean_churn_probability)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-ink-soft">Mean predicted CLV</div>
                  <div className="tabular mt-0.5 text-xl font-semibold text-value">
                    {formatCurrency(segment.mean_predicted_clv)}
                  </div>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
