"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";
import { useProjectProgress } from "@/hooks/useProjectProgress";
import {
  STAGE_ORDER,
  mapActiveByStage,
  useRunningStages,
  type StageKey,
} from "@/hooks/useLiveRun";

/** Short chip labels for the chat header (the five canonical stages —
 * Judge/Plates live inside the crew graph as tools, not fake stages). */
const CHIP_LABELS: Record<StageKey, string> = {
  script: "Script",
  characters: "Cast",
  storyboard: "Board",
  generate: "Gen",
  export: "Export",
};

/** Horizontal pipeline strip in the Showrunner chat header. Reads the SAME
 * run-state store + progress query as the dock and the crew modal, so it can
 * never disagree with them: done stages stay green across refreshes and dock
 * close/reopen, every live stage pulses (not just an arbitrary first one). */
export function PipelineFlow({ projectId }: { projectId: string }) {
  const progress = useProjectProgress(projectId);
  const running = useRunningStages(projectId);
  const activeByStage = useMemo(() => mapActiveByStage(running), [running]);

  return (
    <div className="flex flex-wrap items-center gap-1 gap-y-1.5">
      {STAGE_ORDER.map((key, i) => {
        const active = Boolean(activeByStage[key]);
        const stale = !active && Boolean(progress?.stale?.[key]);
        const done = !active && !stale && Boolean(progress?.[key]);
        return (
          <div key={key} className="flex items-center gap-1">
            <span
              title={
                stale
                  ? "An earlier stage was redone after this one ran. Re-run it to catch up."
                  : undefined
              }
              className={cn(
                "rounded px-1.5 py-0.5 text-[9px] font-medium transition-colors",
                active
                  ? "bg-primary text-primary-foreground motion-safe:animate-pulse"
                  : stale
                    ? "bg-warn/20 text-warn"
                    : done
                      ? "bg-ok/20 text-ok"
                      : "bg-secondary text-muted-foreground"
              )}
            >
              {CHIP_LABELS[key]}
              {stale && " ↺"}
            </span>
            {i < STAGE_ORDER.length - 1 && (
              <span className={cn("h-px w-1.5", done ? "bg-ok/40" : "bg-border")} />
            )}
          </div>
        );
      })}
    </div>
  );
}
