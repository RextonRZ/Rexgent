"use client";

import { cn } from "@/lib/utils";

/** A film-slate empty state: tells the user exactly what this stage makes
 * and hands them the one action that starts it. */
export function EmptyState({
  icon,
  title,
  line,
  children,
  className,
}: {
  icon?: React.ReactNode;
  title: string;
  line: string;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "relative flex flex-col items-center justify-center gap-3 overflow-hidden rounded-2xl border border-dashed hairline bg-card/60 px-8 py-14 text-center",
        className
      )}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 -bottom-24 h-48 rounded-full bg-primary/[0.07] blur-3xl"
      />
      {icon && <div className="relative text-3xl">{icon}</div>}
      <div className="relative">
        <p className="text-base font-semibold">{title}</p>
        <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">{line}</p>
      </div>
      {children && <div className="relative mt-1">{children}</div>}
    </div>
  );
}
