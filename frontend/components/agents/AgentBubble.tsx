"use client";

import { FloatingPanel } from "@/components/shared/FloatingPanel";
import { PipelineFlow } from "./PipelineFlow";
import { useAgentReports, useAgentRegistry } from "@/hooks/useAgents";
import { useActivityFeed } from "@/hooks/useActivityFeed";
import { cn } from "@/lib/utils";

const NAV_H = 56; // header height (h-14) so the panel opens below the nav

function confColor(c: number) {
  if (c >= 0.75) return "bg-ok";
  if (c >= 0.4) return "bg-warn";
  return "bg-bad";
}
function stageFromEvent(e: string): string | null {
  if (e.startsWith("casting.")) return "casting";
  if (e.startsWith("generation.")) return "generation";
  if (e.startsWith("export.") || e.startsWith("audio.mix.")) return "export";
  if (e.startsWith("audio.")) return "audio";
  return null;
}

export function AgentBubble({ projectId }: { projectId: string }) {
  const reports = useAgentReports(projectId);
  const { data: registry } = useAgentRegistry();
  const items = useActivityFeed(projectId);

  const current =
    reports[reports.length - 1]?.stage ??
    [...items].reverse().map((i) => stageFromEvent(i.event)).find(Boolean) ??
    null;

  const recent = reports.slice(-6).reverse();

  return (
    <FloatingPanel
      side="top-right"
      title="Agent activity"
      storageKey="rx.agent.open"
      topOffset={NAV_H}
      width={300}
      pill={
        <>
          <span className="h-2 w-2 rounded-full bg-ok" />
          Agent activity
          {reports.length > 0 && (
            <span className="rounded-full bg-primary text-primary-foreground text-[10px] px-1.5">
              {reports.length}
            </span>
          )}
        </>
      }
    >
      <div className="space-y-3">
        <div>
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1.5">
            Current: {current ?? "idle"}
          </p>
          <PipelineFlow current={current} />
        </div>

        <div className="border-t hairline pt-2 space-y-2">
          {recent.length === 0 ? (
            <p className="text-xs text-muted-foreground">Waiting for agent activity…</p>
          ) : (
            recent.map((r, i) => {
              const name = registry?.find((a) => a.key === r.agent)?.name || r.agent;
              const pct = Math.round(Math.min(Math.max(r.confidence, 0), 1) * 100);
              return (
                <div key={`${r.agent}-${i}`} className="text-xs space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{name}</span>
                    <span className="text-[10px] text-primary/80">{r.stage}</span>
                  </div>
                  {r.rationale && (
                    <p className="text-[11px] text-muted-foreground line-clamp-2">
                      {r.rationale}
                    </p>
                  )}
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 rounded-full bg-secondary overflow-hidden">
                      <div
                        className={cn("h-full rounded-full", confColor(r.confidence))}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="w-8 text-right text-[10px] text-muted-foreground tabular-nums">
                      {pct}%
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </FloatingPanel>
  );
}
