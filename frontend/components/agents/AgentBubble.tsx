"use client";

import { FloatingPanel } from "@/components/shared/FloatingPanel";
import { PipelineFlow } from "./PipelineFlow";
import { useAgentReports, useAgentRegistry, type AgentReport } from "@/hooks/useAgents";
import { useActivityFeed } from "@/hooks/useActivityFeed";

const NAV_H = 56; // header height (h-14) so the panel opens below the nav

function stageFromEvent(e: string): string | null {
  if (e.startsWith("casting.")) return "casting";
  if (e.startsWith("generation.")) return "generation";
  if (e.startsWith("export.") || e.startsWith("audio.mix.")) return "export";
  if (e.startsWith("audio.")) return "audio";
  return null;
}

interface Step {
  agent: string;
  stage: string;
  passed: boolean;
  count: number;
  pct: number;
  rationale?: string | null;
}

/** Collapse consecutive same-agent passes into one step with a count, like a
 *  process log — so "Continuity passed x4" is one line, not four. */
function buildSteps(reports: AgentReport[]): Step[] {
  const steps: Step[] = [];
  for (const r of reports) {
    const passed = /pass/i.test(r.rationale ?? "") || (r.confidence ?? 0) >= 0.7;
    const pct = Math.round(Math.min(Math.max(r.confidence ?? 0, 0), 1) * 100);
    const last = steps[steps.length - 1];
    if (passed && last?.passed && last.agent === r.agent && last.stage === r.stage) {
      last.count += 1;
      last.pct = pct;
    } else {
      steps.push({ agent: r.agent, stage: r.stage, passed, count: 1, pct, rationale: r.rationale });
    }
  }
  return steps;
}

export function AgentBubble({ projectId }: { projectId: string }) {
  const reports = useAgentReports(projectId);
  const { data: registry } = useAgentRegistry();
  const items = useActivityFeed(projectId);

  const current =
    reports[reports.length - 1]?.stage ??
    [...items].reverse().map((i) => stageFromEvent(i.event)).find(Boolean) ??
    null;

  const steps = buildSteps(reports).slice(-8).reverse();
  const name = (key: string) => registry?.find((a) => a.key === key)?.name || key;

  return (
    <FloatingPanel
      side="top-right"
      title="Agent activity"
      storageKey="rx.agent.open"
      topOffset={NAV_H}
      width={360}
      pill={
        <>
          <span className="h-2 w-2 rounded-full bg-ok" />
          Agent activity
          {steps.length > 0 && (
            <span className="rounded-full bg-primary text-primary-foreground text-[10px] px-1.5">
              {steps.length}
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

        <div className="border-t hairline pt-2 space-y-1.5">
          {steps.length === 0 ? (
            <p className="text-xs text-muted-foreground">Waiting for agent activity…</p>
          ) : (
            steps.map((s, i) =>
              s.passed ? (
                // collapsed done step — one muted line
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className="text-ok">✓</span>
                  <span className="font-medium">{name(s.agent)}</span>
                  <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">
                    {s.count > 1 ? `${s.count}× ` : ""}
                    {s.stage} · {s.pct}%
                  </span>
                </div>
              ) : (
                // flagged / low-confidence — show why
                <div key={i} className="text-xs space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="text-warn">●</span>
                    <span className="font-medium">{name(s.agent)}</span>
                    <span className="ml-auto text-[10px] text-warn tabular-nums">
                      {s.stage} · {s.pct}%
                    </span>
                  </div>
                  {s.rationale && (
                    <p className="pl-5 text-[11px] text-muted-foreground line-clamp-2">
                      {s.rationale}
                    </p>
                  )}
                </div>
              )
            )
          )}
        </div>
      </div>
    </FloatingPanel>
  );
}
