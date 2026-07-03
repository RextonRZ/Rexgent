"use client";

import { cn } from "@/lib/utils";

const STAGES = [
  { key: "script", label: "Script" },
  { key: "judge", label: "Judge" },
  { key: "characters", label: "Cast" },
  { key: "storyboard", label: "Board" },
  { key: "casting", label: "Plates" },
  { key: "generation", label: "Gen" },
  { key: "export", label: "Export" },
];

/** Horizontal pipeline; the current stage is highlighted + pulsing ("live direction"). */
export function PipelineFlow({ current }: { current: string | null }) {
  const idx = STAGES.findIndex((s) => s.key === current);
  return (
    <div className="flex items-center gap-1 gap-y-1.5 flex-wrap">
      {STAGES.map((s, i) => {
        const active = i === idx;
        const done = idx > -1 && i < idx;
        return (
          <div key={s.key} className="flex items-center gap-1">
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-[9px] font-medium transition-colors",
                active
                  ? "bg-primary text-primary-foreground animate-pulse"
                  : done
                  ? "bg-ok/20 text-ok"
                  : "bg-secondary text-muted-foreground"
              )}
            >
              {s.label}
            </span>
            {i < STAGES.length - 1 && (
              <span className={cn("h-px w-1.5", done ? "bg-ok/40" : "bg-border")} />
            )}
          </div>
        );
      })}
    </div>
  );
}
