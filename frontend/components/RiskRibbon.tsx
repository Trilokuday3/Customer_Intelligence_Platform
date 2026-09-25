import { formatNumber } from "@/lib/format";
import { RISK_BANDS, riskBand } from "@/lib/risk";
import type { RiskBin } from "@/lib/types";

/** Distribution of churn probability across all scored customers, each bar
 * coloured by its risk band. Server-rendered CSS bars: no chart library. */
export default function RiskRibbon({ bins, total }: { bins: RiskBin[]; total: number }) {
  const max = Math.max(...bins.map((b) => b.count), 1);
  const bandCounts = RISK_BANDS.map((band) => ({
    band,
    count: bins
      .filter((b) => riskBand((b.lower + b.upper) / 2).key === band.key)
      .reduce((sum, b) => sum + b.count, 0),
  }));

  return (
    <div>
      <div
        className="flex h-44 items-end gap-[3px]"
        role="img"
        aria-label="Distribution of churn probability across scored customers"
      >
        {bins.map((bin, index) => {
          const band = riskBand((bin.lower + bin.upper) / 2);
          return (
            <div
              key={bin.lower}
              className="ribbon-bar flex-1 rounded-t-[3px]"
              style={{
                height: `${Math.max((bin.count / max) * 100, bin.count > 0 ? 2 : 0)}%`,
                backgroundColor: band.color,
                animationDelay: `${index * 25}ms`,
              }}
              title={`${Math.round(bin.lower * 100)}-${Math.round(bin.upper * 100)}% churn probability: ${formatNumber(bin.count)} customers`}
            />
          );
        })}
      </div>
      <div className="tabular mt-2 flex justify-between text-xs text-ink-soft">
        <span>0%</span>
        <span>25%</span>
        <span>50%</span>
        <span>75%</span>
        <span>100%</span>
      </div>
      <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-sm">
        {bandCounts.map(({ band, count }) => (
          <li key={band.key} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: band.color }} aria-hidden />
            <span className="text-ink-soft">{band.label}</span>
            <span className="tabular font-medium">{formatNumber(count)}</span>
            <span className="tabular text-xs text-ink-soft">({total ? Math.round((count / total) * 100) : 0}%)</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
