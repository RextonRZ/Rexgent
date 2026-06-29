"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const STEPS = [
  { n: 1, label: "Script", path: "script" },
  { n: 2, label: "Characters", path: "characters" },
  { n: 3, label: "Storyboard", path: "storyboard" },
  { n: 4, label: "Generate", path: "generate" },
  { n: 5, label: "Edit", path: "edit" },
  { n: 6, label: "Export", path: "export" },
];

export function PipelineNav({ projectId }: { projectId: string }) {
  const pathname = usePathname() || "";
  const activeIndex = STEPS.findIndex((s) => pathname.includes(`/${s.path}`));

  return (
    <nav className="flex items-center gap-0.5 sm:gap-1">
      {STEPS.map((step, i) => {
        const isActive = i === activeIndex;
        const isDone = activeIndex > -1 && i < activeIndex;
        return (
          <div key={step.path} className="flex items-center">
            <Link
              href={`/projects/${projectId}/${step.path}`}
              className={cn(
                "group flex items-center gap-2 rounded-full px-2.5 py-1.5 transition-colors",
                isActive ? "bg-primary/15" : "hover:bg-white/5"
              )}
            >
              <span
                className={cn(
                  "flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : isDone
                    ? "bg-ok/20 text-ok"
                    : "bg-secondary text-muted-foreground"
                )}
              >
                {isDone ? "✓" : step.n}
              </span>
              <span
                className={cn(
                  "text-xs font-medium hidden md:inline",
                  isActive
                    ? "text-foreground"
                    : "text-muted-foreground group-hover:text-foreground"
                )}
              >
                {step.label}
              </span>
            </Link>
            {i < STEPS.length - 1 && (
              <span
                className={cn(
                  "h-px w-2 sm:w-4",
                  isDone ? "bg-ok/40" : "bg-border"
                )}
              />
            )}
          </div>
        );
      })}
    </nav>
  );
}
