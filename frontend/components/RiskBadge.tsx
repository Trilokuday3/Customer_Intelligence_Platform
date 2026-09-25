import { formatPercent } from "@/lib/format";
import { riskBand } from "@/lib/risk";

/** Pill with the band colour, the percentage and a small meter. */
export default function RiskBadge({ probability }: { probability: number | null }) {
  if (probability === null) {
    return <span className="text-xs text-ink-soft">Not scored</span>;
  }
  const band = riskBand(probability);
  return (
    <span className="inline-flex items-center gap-2.5" title={`${band.label} risk`}>
      <span
        className="tabular inline-flex min-w-[3.75rem] items-center justify-center rounded-full px-2 py-0.5 text-xs font-semibold"
        style={{ backgroundColor: band.soft, color: band.color }}
      >
        {formatPercent(probability)}
      </span>
      <span className="hidden h-1.5 w-16 overflow-hidden rounded-full bg-line sm:block" aria-hidden>
        <span
          className="block h-full rounded-full"
          style={{ width: `${Math.round(probability * 100)}%`, backgroundColor: band.color }}
        />
      </span>
    </span>
  );
}
