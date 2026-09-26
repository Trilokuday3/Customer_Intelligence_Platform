export interface BarItem {
  label: string;
  /** Bar length as a fraction of the track, 0..1. */
  fraction: number;
  /** Text shown at the end of the row. */
  display: string;
  color: string;
}

/** Horizontal bars as plain HTML: they fill whatever width the panel has, so
 * they read the same on a phone and a desktop, and need no chart library. */
export default function BarList({ items, label }: { items: BarItem[]; label: string }) {
  return (
    <ul className="flex flex-col gap-3.5" aria-label={label}>
      {items.map((item) => (
        <li key={item.label} className="grid grid-cols-[minmax(6.5rem,9rem)_1fr_auto] items-center gap-3 text-sm">
          <span className="capitalize leading-tight">{item.label}</span>
          <span className="h-3 overflow-hidden rounded-full bg-paper" aria-hidden>
            <span
              className="block h-full rounded-full"
              style={{ width: `${Math.max(item.fraction, 0.01) * 100}%`, backgroundColor: item.color }}
            />
          </span>
          <span className="tabular min-w-[3.25rem] text-right font-semibold">{item.display}</span>
        </li>
      ))}
    </ul>
  );
}
