type Tone = "ink" | "risk" | "retain" | "value";

const TONE_COLOR: Record<Tone, string> = {
  ink: "text-ink",
  risk: "text-risk",
  retain: "text-retain",
  value: "text-value",
};

export default function StatTile({
  label,
  value,
  tone = "ink",
  sublabel,
}: {
  label: string;
  value: string;
  tone?: Tone;
  sublabel?: string;
}) {
  return (
    <div className="border-b-2 border-line pb-3">
      <div className={`tabular text-3xl font-medium ${TONE_COLOR[tone]}`}>{value}</div>
      <div className="mt-1 text-sm text-ink-soft">{label}</div>
      {sublabel ? <div className="text-xs text-ink-soft/70">{sublabel}</div> : null}
    </div>
  );
}
