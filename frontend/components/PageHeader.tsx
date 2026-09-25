import type { ReactNode } from "react";

export default function PageHeader({
  title,
  description,
  meta,
  back,
}: {
  title: string;
  description?: ReactNode;
  meta?: ReactNode;
  back?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="max-w-2xl">
        {back ? <div className="mb-2 text-sm">{back}</div> : null}
        <h1 className="text-[26px] font-semibold leading-tight tracking-tight">{title}</h1>
        {description ? <p className="mt-1.5 text-sm leading-relaxed text-ink-soft">{description}</p> : null}
      </div>
      {meta ? <div className="shrink-0">{meta}</div> : null}
    </div>
  );
}

/** Small "data as of" chip shown at the top right of data pages. */
export function AsOfChip({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink-soft">
      <span className="h-1.5 w-1.5 rounded-full bg-healthy" aria-hidden />
      {label}
    </span>
  );
}
