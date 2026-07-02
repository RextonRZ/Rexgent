"use client";

import { useLedger } from "@/hooks/useLedger";
import { useActivityFeed } from "@/hooks/useActivityFeed";
import { cn } from "@/lib/utils";

const CATEGORIES: { key: string; label: string }[] = [
  { key: "llm", label: "LLM" },
  { key: "image", label: "Image" },
  { key: "video", label: "Video" },
  { key: "tts", label: "TTS" },
];

const STAGES: { key: string; label: string }[] = [
  { key: "casting", label: "Casting" },
  { key: "audio", label: "Audio" },
  { key: "generation", label: "Generation" },
  { key: "export", label: "Export" },
];

type StageStatus = "pending" | "running" | "done";

const STAGE_STATUS_MAP: Record<string, { cls: string; label: string }> = {
  pending: { cls: "bg-secondary text-muted-foreground", label: "Pending" },
  running: { cls: "bg-warn/15 text-warn", label: "Running" },
  done: { cls: "bg-ok/15 text-ok", label: "Done" },
};

function eventToStage(event: string): string | null {
  if (event.startsWith("casting.")) return "casting";
  if (event.startsWith("generation.")) return "generation";
  if (event.startsWith("export.") || event.startsWith("audio.mix.")) return "export";
  if (event.startsWith("audio.")) return "audio";
  return null;
}

function eventToStatus(event: string): StageStatus | null {
  if (event.includes("started")) return "running";
  if (event.includes("completed")) return "done";
  return null;
}

function useStageStatuses(projectId: string): Record<string, StageStatus> {
  const items = useActivityFeed(projectId);
  const statuses: Record<string, StageStatus> = {};
  for (const item of items) {
    const stage = eventToStage(item.event);
    const status = eventToStatus(item.event);
    if (!stage || !status) continue;
    // Later events win, but never downgrade "done" back to "running".
    if (statuses[stage] === "done" && status === "running") continue;
    statuses[stage] = status;
  }
  return statuses;
}

export function CostLedger({ projectId }: { projectId: string }) {
  const ledger = useLedger(projectId);
  const stageStatuses = useStageStatuses(projectId);

  const byCategory = ledger?.by_category ?? {};
  const byStage = ledger?.by_stage ?? {};
  const grandTotal = ledger?.grand_total ?? 0;
  const budget = ledger?.budget ?? 40;
  const withinBudget = ledger?.within_budget ?? true;
  const maxCategory = Math.max(1, ...CATEGORIES.map((c) => byCategory[c.key] ?? 0));
  const pct = Math.min((grandTotal / (budget || 1)) * 100, 100);

  return (
    <div className="glass rounded-xl p-5 space-y-5">
      {/* grand total */}
      <div>
        <div className="flex items-end justify-between">
          <div>
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              Cost ledger
            </p>
            <p
              className={cn(
                "text-3xl font-bold tabular-nums mt-1",
                !withinBudget && "text-bad"
              )}
            >
              ${grandTotal.toFixed(2)}
              <span className="text-base font-normal text-muted-foreground">
                {" "}
                / ${budget.toFixed(2)}
              </span>
            </p>
          </div>
          {!withinBudget && (
            <span className="text-xs font-medium px-2 py-1 rounded-full bg-bad/15 text-bad">
              over budget
            </span>
          )}
        </div>
        <div className="mt-3 h-2.5 rounded-full bg-secondary overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-500",
              !withinBudget ? "bg-bad" : pct > 70 ? "bg-warn" : "bg-primary"
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* per-category bars */}
      <div className="space-y-2">
        {CATEGORIES.map((c) => {
          const amount = byCategory[c.key] ?? 0;
          const barPct = Math.min((amount / maxCategory) * 100, 100);
          return (
            <div key={c.key} className="flex items-center gap-3 text-xs">
              <span className="w-14 shrink-0 text-muted-foreground">{c.label}</span>
              <div className="flex-1 h-2 rounded-full bg-secondary overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-500"
                  style={{ width: `${barPct}%` }}
                />
              </div>
              <span className="w-14 shrink-0 text-right tabular-nums font-medium">
                ${amount.toFixed(2)}
              </span>
            </div>
          );
        })}
      </div>

      {/* stage table */}
      <div className="border-t hairline pt-3 space-y-2">
        {STAGES.map((s) => {
          const status = stageStatuses[s.key] ?? "pending";
          const chip = STAGE_STATUS_MAP[status];
          const amount = byStage[s.key] ?? 0;
          return (
            <div key={s.key} className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">{s.label}</span>
              <div className="flex items-center gap-2">
                <span className={cn("rounded-full px-2 py-0.5 font-medium", chip.cls)}>
                  {chip.label}
                </span>
                <span className="w-12 text-right tabular-nums font-medium">
                  ${amount.toFixed(2)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
