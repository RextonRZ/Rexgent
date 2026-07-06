"use client";

import { cn } from "@/lib/utils";

/** The app pages' shared masthead: the landing page's confidence carried
 * inside — big tight title, one quiet line under it, actions on the right,
 * and a faint violet wash so pages don't open on dead flat black. */
export function PageHeader({
  title,
  sub,
  children,
  className,
}: {
  title: string;
  sub?: string;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "relative flex flex-wrap items-end justify-between gap-3 overflow-hidden rounded-2xl border hairline bg-card px-5 py-4",
        className
      )}
    >
      {/* quiet cinematic wash, echoing the landing hero */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-16 left-1/4 h-40 w-1/2 rounded-full bg-primary/10 blur-3xl"
      />
      <div className="relative">
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {sub && <p className="mt-0.5 text-sm text-muted-foreground">{sub}</p>}
      </div>
      {children && (
        <div className="relative flex flex-wrap items-center gap-2.5">{children}</div>
      )}
    </div>
  );
}
