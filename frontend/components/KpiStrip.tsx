type Tone = "ink" | "critical" | "value" | "healthy";

const TONE: Record<Tone, string> = {
  ink: "text-ink",
  critical: "text-critical",
  value: "text-value",
  healthy: "text-healthy",
};

export interface Kpi {
  label: string;
  value: string;
  tone?: Tone;
  note?: string;
}

/** One continuous strip of headline numbers instead of a row of identical
 * cards. Cell borders (trimmed at the edges by the clipped wrapper) keep the
 * dividers clean whatever the number of columns. */
export default function KpiStrip({ items }: { items: Kpi[] }) {
  return (
    <div className="min-w-0 overflow-hidden rounded-[10px] border border-line bg-surface">
      <div className="-mb-px -mr-px grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5">
        {items.map((item) => (
          <div key={item.label} className="min-w-0 border-b border-r border-line px-5 py-4">
            <div className="text-[13px] text-ink-soft">{item.label}</div>
            <div
              className={`tabular mt-1 text-[26px] font-semibold leading-tight tracking-tight sm:text-[28px] ${TONE[item.tone ?? "ink"]}`}
            >
              {item.value}
            </div>
            {item.note ? <div className="mt-0.5 text-xs text-ink-soft">{item.note}</div> : null}
          </div>
        ))}
      </div>
    </div>
  );
}
