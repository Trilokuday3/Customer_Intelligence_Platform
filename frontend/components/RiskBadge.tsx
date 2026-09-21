import { formatPercent } from "@/lib/format";

export default function RiskBadge({ probability }: { probability: number | null }) {
  if (probability === null) {
    return <span className="tabular text-xs text-ink-soft">—</span>;
  }
  const tone = probability >= 0.5 ? "bg-risk-soft text-risk" : "bg-retain-soft text-retain";
  return (
    <span className={`tabular inline-block rounded px-2 py-0.5 text-xs font-medium ${tone}`}>
      {formatPercent(probability)}
    </span>
  );
}
