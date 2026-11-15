import Link from "next/link";
import type { ReactNode } from "react";

export function AppShell({
  children,
  title = "veriθ",
  subtitle,
}: {
  children: ReactNode;
  title?: string;
  subtitle?: string;
}) {
  return (
    <div className="app-shell min-h-screen text-slate-900">
      <header className="border-b border-slate-100 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-5 sm:px-8">
          <Link href="/" className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-2xl bg-[var(--brand)] text-lg font-semibold text-white">
              θ
            </div>
            <div>
              <p className="text-sm font-semibold tracking-[0.16em] text-[var(--brand)] uppercase">
                veriθ
              </p>
              <p className="hidden text-xs text-slate-500 sm:block">Evidence-based AI Stock Research</p>
            </div>
          </Link>
          <Link
            href="/research"
            className="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-2xl bg-[var(--brand)] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-[var(--brand-hover)]"
          >
            AI 리서치
          </Link>
        </div>
      </header>

      <main className="app-shell-main mx-auto flex w-full max-w-6xl flex-col gap-7 px-5 py-10 sm:gap-9 sm:px-8 sm:py-14">
        <div className="space-y-3">
          <h1 className="text-3xl font-bold leading-tight tracking-tight text-slate-950 sm:text-4xl">{title}</h1>
          {subtitle ? <p className="max-w-2xl text-sm leading-7 text-slate-600 sm:text-base">{subtitle}</p> : null}
        </div>
        {children}
      </main>
    </div>
  );
}
