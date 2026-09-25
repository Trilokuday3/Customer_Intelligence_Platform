import type { ReactNode } from "react";

export default function Panel({
  title,
  description,
  action,
  children,
  flush = false,
  className = "",
}: {
  title?: string;
  description?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  flush?: boolean;
  className?: string;
}) {
  return (
    <section className={`min-w-0 rounded-[10px] border border-line bg-surface ${className}`}>
      {title ? (
        <div className="flex items-start justify-between gap-4 px-5 pt-4">
          <div>
            <h2 className="text-[15px] font-semibold tracking-tight">{title}</h2>
            {description ? <p className="mt-0.5 text-[13px] text-ink-soft">{description}</p> : null}
          </div>
          {action}
        </div>
      ) : null}
      <div className={flush ? "mt-3 overflow-x-auto" : "p-5 pt-3"}>{children}</div>
    </section>
  );
}
