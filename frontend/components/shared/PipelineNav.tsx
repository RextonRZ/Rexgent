"use client";

import { useState } from "react";
import { GoLink as Link } from "@/components/shared/NavProgress";
import { usePathname } from "next/navigation";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  useProjectProgress,
  type ProjectProgress,
} from "@/hooks/useProjectProgress";

const STEPS: { n: number; label: string; path: string; key: keyof ProjectProgress }[] = [
  { n: 1, label: "Script", path: "script", key: "script" },
  { n: 2, label: "Characters", path: "characters", key: "characters" },
  { n: 3, label: "Storyboard", path: "storyboard", key: "storyboard" },
  { n: 4, label: "Generate", path: "generate", key: "generate" },
  { n: 5, label: "Edit & Export", path: "export", key: "export" },
];

export function PipelineNav({ projectId }: { projectId: string }) {
  const pathname = usePathname() || "";
  const progress = useProjectProgress(projectId);
  const [expanded, setExpanded] = useState(false);
  const activeIndex = Math.max(
    0,
    STEPS.findIndex((s) => pathname.includes(`/${s.path}`))
  );

  // a step is "done" only when its artifact actually exists — not merely walked past
  const isDone = (i: number) =>
    progress ? Boolean(progress[STEPS[i].key]) : i < activeIndex;

  return (
    <>
      {/* ── full stepper (lg+) ─────────────────────────────────────── */}
      <nav className="hidden lg:flex items-center" aria-label="Pipeline steps">
        {STEPS.map((step, i) => {
          const active = i === activeIndex;
          const done = isDone(i) && !active;
          return (
            <div key={step.path} className="flex items-center">
              {i > 0 && (
                // the segment behind completed steps fills violet — the nav
                // doubles as a progress bar
                <span
                  className={cn(
                    "h-0.5 w-4 xl:w-8 rounded-full transition-colors",
                    isDone(i - 1) || active || i <= activeIndex
                      ? "bg-primary/70"
                      : "bg-white/10"
                  )}
                />
              )}
              <Link
                href={`/projects/${projectId}/${step.path}`}
                aria-current={active ? "step" : undefined}
                className={cn(
                  "group relative flex items-center gap-2 rounded-full px-2.5 py-1.5 transition-colors",
                  active ? "bg-primary/10" : "hover:bg-white/5"
                )}
              >
                <span
                  className={cn(
                    "flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold transition-colors",
                    active
                      ? "bg-primary text-primary-foreground shadow-[0_0_12px_rgba(139,92,246,0.55)]"
                      : done
                      ? "bg-ok/15 text-ok"
                      : "border border-white/15 text-muted-foreground"
                  )}
                >
                  {done ? <Check className="size-3.5" /> : step.n}
                </span>
                <span
                  className={cn(
                    "text-sm transition-colors",
                    active
                      ? "font-medium text-foreground"
                      : done
                      ? "text-foreground/80 group-hover:text-foreground"
                      : "text-muted-foreground group-hover:text-foreground"
                  )}
                >
                  {step.label}
                </span>
                {active && (
                  <span className="absolute inset-x-2.5 -bottom-px h-0.5 rounded-full bg-primary" />
                )}
              </Link>
            </div>
          );
        })}
      </nav>

      {/* ── compact form (below lg): Step N of 5 · Label + progress ──── */}
      <div className="relative lg:hidden">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-2.5 rounded-full px-3 py-1.5 hover:bg-white/5 transition-colors"
          aria-expanded={expanded}
        >
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground shadow-[0_0_10px_rgba(139,92,246,0.5)]">
            {activeIndex + 1}
          </span>
          <span className="flex flex-col items-start leading-tight">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Step {activeIndex + 1} of {STEPS.length}
            </span>
            <span className="text-sm font-medium text-foreground">
              {STEPS[activeIndex].label}
            </span>
          </span>
          <ChevronDown
            className={cn(
              "size-4 text-muted-foreground transition-transform",
              expanded && "rotate-180"
            )}
          />
        </button>
        {/* thin progress bar under the compact label */}
        <span className="absolute inset-x-3 -bottom-0.5 h-0.5 rounded-full bg-white/10">
          <span
            className="block h-full rounded-full bg-primary transition-[width] duration-300"
            style={{ width: `${((activeIndex + 1) / STEPS.length) * 100}%` }}
          />
        </span>

        {expanded && (
          <>
            <div
              className="fixed inset-0 z-40"
              onClick={() => setExpanded(false)}
            />
            <div className="absolute left-0 top-full z-50 mt-2 w-56 overflow-hidden rounded-xl border hairline bg-background/95 p-1 shadow-2xl shadow-black/50 backdrop-blur">
              {STEPS.map((step, i) => {
                const active = i === activeIndex;
                const done = isDone(i) && !active;
                return (
                  <Link
                    key={step.path}
                    href={`/projects/${projectId}/${step.path}`}
                    onClick={() => setExpanded(false)}
                    className={cn(
                      "flex items-center gap-3 rounded-lg px-2.5 py-2 transition-colors",
                      active ? "bg-primary/10" : "hover:bg-white/5"
                    )}
                  >
                    <span
                      className={cn(
                        "flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-bold",
                        active
                          ? "bg-primary text-primary-foreground"
                          : done
                          ? "bg-ok/15 text-ok"
                          : "border border-white/15 text-muted-foreground"
                      )}
                    >
                      {done ? <Check className="size-3" /> : step.n}
                    </span>
                    <span
                      className={cn(
                        "text-sm",
                        active
                          ? "font-medium text-foreground"
                          : "text-muted-foreground"
                      )}
                    >
                      {step.label}
                    </span>
                  </Link>
                );
              })}
            </div>
          </>
        )}
      </div>
    </>
  );
}
