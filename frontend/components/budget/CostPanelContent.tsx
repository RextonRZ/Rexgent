"use client";

import { useLedger } from "@/hooks/useLedger";
import { useActivityFeed } from "@/hooks/useActivityFeed";
import { cn } from "@/lib/utils";

const CATEGORIES = [
  { key: "llm", label: "LLM" },
  { key: "image", label: "Image" },
  { key: "video", label: "Video" },
  { key: "tts", label: "TTS" },
];
const STAGES = [
  { key: "casting", label: "Casting" },
  { key: "audio", label: "Audio" },
  { key: "generation", label: "Generation" },
  { key: "export", label: "Export" },
];
type StageStatus = "pending" | "running" | "done";
const STATUS_CHIP: Record<StageStatus, { cls: string; label: string }> = {
  pending: { cls: "bg-secondary text-muted-foreground", label: "Pending" },
  running: { cls: "bg-warn/15 text-warn", label: "Running" },
  done: { cls: "bg-ok/15 text-ok", label: "Done" },
};

function eventToStage(e: string): string | null {
  if (e.startsWith("casting.")) return "casting";
  if (e.startsWith("generation.")) return "generation";
  if (e.startsWith("export.") || e.startsWith("audio.mix.")) return "export";
  if (e.startsWith("audio.")) return "audio";
  return null;
}
function eventToStatus(e: string): StageStatus | null {
  if (e.includes("started")) return "running";
  if (e.includes("completed")) return "done";
  return null;
}

/** Full cost ledger: total, per-category bars, per-stage status rows. */
export function CostPanelContent({ projectId }: { projectId: string }) {
  const ledger = useLedger(projectId);
  const items = useActivityFeed(projectId);

  const statuses: Record<string, StageStatus> = {};
  for (const it of items) {
    const st = eventToStage(it.event);
    const s = eventToStatus(it.event);
    if (!st || !s) continue;
    if (statuses[st] === "done" && s === "running") continue;
    statuses[st] = s;
  }

  const byCat = ledger?.by_category ?? {};
  const byStage = ledger?.by_stage ?? {};
  const grand = ledger?.grand_total ?? 0;
  const budget = ledger?.budget ?? 40;
  const within = ledger?.within_budget ?? true;
  const maxCat = Math.max(1, ...CATEGORIES.map((c) => byCat[c.key] ?? 0));
  const pct = Math.min((grand / (budget || 1)) * 100, 100);

  return (
    <div className="space-y-4">
      <div>
        <p className={cn("text-2xl font-bold tabular-nums", !within && "text-bad")}>
          ${grand.toFixed(2)}
          <span className="text-sm font-normal text-muted-foreground">
            {" "}
            / ${budget.toFixed(2)}
          </span>
        </p>
        <div className="mt-2 h-2 rounded-full bg-secondary overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full",
              !within ? "bg-bad" : pct > 70 ? "bg-warn" : "bg-primary"
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <div className="space-y-1.5">
        {CATEGORIES.map((c) => {
          const amt = byCat[c.key] ?? 0;
          return (
            <div key={c.key} className="flex items-center gap-2 text-xs">
              <span className="w-12 text-muted-foreground">{c.label}</span>
              <div className="flex-1 h-1.5 rounded-full bg-secondary overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${Math.min((amt / maxCat) * 100, 100)}%` }}
                />
              </div>
              <span className="w-12 text-right tabular-nums">${amt.toFixed(2)}</span>
            </div>
          );
        })}
      </div>

      <div className="border-t hairline pt-2 space-y-1.5">
        {STAGES.map((s) => {
          const chip = STATUS_CHIP[statuses[s.key] ?? "pending"];
          return (
            <div key={s.key} className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">{s.label}</span>
              <div className="flex items-center gap-2">
                <span className={cn("rounded-full px-2 py-0.5", chip.cls)}>
                  {chip.label}
                </span>
                <span className="w-12 text-right tabular-nums">
                  ${(byStage[s.key] ?? 0).toFixed(2)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
