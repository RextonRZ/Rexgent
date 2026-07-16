"use client";

import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { useLedger } from "@/hooks/useLedger";
import { useActivityFeed } from "@/hooks/useActivityFeed";
import { cn } from "@/lib/utils";

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${Math.round(n / 1_000)}K`;
  return String(n);
}

const TIER_DOT: Record<string, string> = {
  flash: "bg-emerald-400",
  plus: "bg-sky-400",
  max: "bg-violet-400",
};

function tierOf(model: string): string {
  const m = model.toLowerCase();
  if (m.includes("flash") || m.includes("turbo")) return "flash";
  if (m.includes("plus")) return "plus";
  return "max";
}

const CATEGORIES = [
  { key: "llm", label: "LLM", unit: "" },
  { key: "image", label: "Image", unit: "img" },
  { key: "video", label: "Video", unit: "s" },
  { key: "tts", label: "Voice", unit: "ch" },
];

function fmtQty(q: number, unit: string): string {
  const n = q >= 1000 ? `${Math.round(q / 1000)}K` : String(Math.round(q));
  return unit ? `${n}${unit === "img" ? " img" : unit}` : n;
}
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
  const [openCats, setOpenCats] = useState<Set<string>>(new Set());
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

      {ledger?.llm && ledger.llm.total_tokens > 0 && (
        <div className="rounded-lg bg-white/[0.03] px-3 py-2">
          <div className="flex items-baseline justify-between">
            <span className="text-xs text-muted-foreground">Tokens</span>
            <span className="text-sm font-semibold tabular-nums">
              {fmtTokens(ledger.llm.total_tokens)}
            </span>
          </div>
          <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
            {Object.entries(ledger.llm.by_model).map(([model, v]) => (
              <span key={model} className="inline-flex items-center gap-1 text-[11px]">
                <span className={cn("h-1.5 w-1.5 rounded-full", TIER_DOT[tierOf(model)])} />
                <span className="text-muted-foreground">{model}</span>
                <span className="tabular-nums">{fmtTokens(v.tokens)}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-1.5">
        {CATEGORIES.map((c) => {
          const amt = byCat[c.key] ?? 0;
          const models = ledger?.media_models?.[c.key];
          const hasDetail = !!models && Object.keys(models).length > 0;
          const isOpen = openCats.has(c.key);
          const row = (
            <>
              <span className="flex w-14 items-center gap-0.5 text-muted-foreground">
                {hasDetail && (
                  <ChevronRight
                    className={cn(
                      "size-3 shrink-0 transition-transform duration-150",
                      isOpen && "rotate-90"
                    )}
                  />
                )}
                <span className={hasDetail ? "" : "pl-3.5"}>{c.label}</span>
              </span>
              <div className="flex-1 h-1.5 rounded-full bg-secondary overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${Math.min((amt / maxCat) * 100, 100)}%` }}
                />
              </div>
              <span className="w-12 text-right tabular-nums">${amt.toFixed(2)}</span>
            </>
          );
          return (
            <div key={c.key}>
              {hasDetail ? (
                <button
                  onClick={() =>
                    setOpenCats((cur) => {
                      const next = new Set(cur);
                      if (next.has(c.key)) next.delete(c.key);
                      else next.add(c.key);
                      return next;
                    })
                  }
                  aria-expanded={isOpen}
                  className="flex w-full items-center gap-2 rounded text-left text-xs hover:bg-white/[0.03]"
                >
                  {row}
                </button>
              ) : (
                <div className="flex items-center gap-2 text-xs">{row}</div>
              )}
              {/* per-model detail, folded away until asked for */}
              {hasDetail && isOpen && (
                <div className="ml-[62px] mt-1 space-y-0.5 border-l hairline pl-2">
                  {Object.entries(models!)
                    .sort((a, b) => b[1].usd - a[1].usd)
                    .map(([model, v]) => (
                      <div
                        key={model}
                        className="flex items-baseline justify-between gap-2 text-[10px] text-muted-foreground"
                      >
                        <span className="truncate font-mono">{model}</span>
                        <span className="shrink-0 tabular-nums">
                          {fmtQty(v.qty, c.unit)} · ${v.usd.toFixed(2)}
                        </span>
                      </div>
                    ))}
                </div>
              )}
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
