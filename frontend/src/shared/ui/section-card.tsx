import type { ReactNode } from "react";

import clsx from "clsx";

export function SectionCard({
  title,
  subtitle,
  action,
  children,
  className,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={clsx(
        "min-w-0 rounded-3xl bg-white p-6 shadow-[var(--card-shadow)] sm:p-8",
        className,
      )}
    >
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4 sm:mb-8">
        <div className="min-w-0 flex-1 space-y-2">
          <h2 className="text-xl font-bold leading-7 tracking-tight text-slate-950">{title}</h2>
          {subtitle ? <p className="max-w-2xl text-sm leading-6 text-slate-600">{subtitle}</p> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
