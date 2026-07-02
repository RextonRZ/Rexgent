"use client";

import { useEffect, useRef } from "react";
import {
  useAgentReports,
  useAgentRegistry,
  type AgentReport,
} from "@/hooks/useAgents";
import { cn } from "@/lib/utils";

function agentLabel(report: AgentReport, registry: ReturnType<typeof useAgentRegistry>["data"]) {
  const info = registry?.find((a) => a.key === report.agent);
  return info?.name || report.agent;
}

function confidenceColor(confidence: number) {
  if (confidence >= 0.75) return "bg-ok";
  if (confidence >= 0.4) return "bg-warn";
  return "bg-bad";
}

function formatTime(at?: string) {
  if (!at) return "";
  const d = new Date(at);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function AgentDecisionPanel({ projectId }: { projectId: string }) {
  const reports = useAgentReports(projectId);
  const { data: registry } = useAgentRegistry();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [reports.length]);

  return (
    <div className="rounded-xl border hairline bg-card h-full flex flex-col">
      <div className="px-4 py-3 border-b hairline">
        <h2 className="text-sm font-medium">Agent decisions</h2>
        <p className="text-[11px] text-muted-foreground">
          Live reasoning from each agent in the pipeline
        </p>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2 max-h-[520px]">
        {reports.length === 0 ? (
          <p className="text-xs text-muted-foreground">Waiting for agent activity…</p>
        ) : (
          reports.map((report, i) => (
            <div
              key={`${report.agent}-${report.stage}-${i}`}
              className="rounded-lg border hairline bg-background/40 px-2.5 py-2 text-xs space-y-1.5"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{agentLabel(report, registry)}</span>
                <span className="text-[10px] text-muted-foreground shrink-0">
                  {formatTime(report.created_at)}
                </span>
              </div>
              <p className="text-[11px] text-primary/80">{report.stage}</p>
              {report.rationale && (
                <p className="text-[11px] text-muted-foreground">{report.rationale}</p>
              )}
              <div className="flex items-center gap-2 pt-0.5">
                <div className="flex-1 h-1.5 rounded-full bg-secondary overflow-hidden">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all duration-500",
                      confidenceColor(report.confidence)
                    )}
                    style={{ width: `${Math.round(Math.min(Math.max(report.confidence, 0), 1) * 100)}%` }}
                  />
                </div>
                <span className="w-9 shrink-0 text-right tabular-nums text-[10px] text-muted-foreground">
                  {Math.round(Math.min(Math.max(report.confidence, 0), 1) * 100)}%
                </span>
              </div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
