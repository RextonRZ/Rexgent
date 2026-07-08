"use client";

import { useLedger } from "@/hooks/useLedger";
import { cn } from "@/lib/utils";

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(n >= 10_000 ? 0 : 1)}K`;
  return String(n);
}

// Cheap tiers first so the savings story reads left to right.
const TIER_STYLE: Record<string, { dot: string; text: string; order: number }> = {
  flash: { dot: "bg-emerald-400", text: "text-emerald-300", order: 0 },
  plus: { dot: "bg-sky-400", text: "text-sky-300", order: 1 },
  max: { dot: "bg-violet-400", text: "text-violet-300", order: 2 },
};

function tierOf(model: string): keyof typeof TIER_STYLE {
  const m = model.toLowerCase();
  if (m.includes("flash") || m.includes("turbo")) return "flash";
  if (m.includes("plus")) return "plus";
  return "max";
}

const STAGE_LABELS: Record<string, string> = {
  script: "Script",
  structure: "Structuring",
  characters: "Characters",
  storyboard: "Storyboard",
  judge: "Judge",
  plot_gap: "Plot gaps",
  ending: "Ending",
  prompt_craft: "Prompt craft",
  wardrobe: "Wardrobe",
  relationships: "Relationships",
  clarify: "Clarification",
  continuity: "Continuity",
  style: "Style",
  mbti: "MBTI",
  face: "Face",
  regen_rewrite: "Regen",
  title: "Titles",
};

/** The token engineering, made visible: live tokens vs the drama's budget,
 * split by model tier so the cheap routing is provable at a glance. */
export function TokenDashboard({ projectId }: { projectId: string }) {
  const ledger = useLedger(projectId);
  const llm = ledger?.llm;
  if (!llm || llm.total_tokens <= 0) return null;

  const grand = ledger?.grand_total ?? 0;
  const budget = ledger?.budget ?? 40;
  const models = Object.entries(llm.by_model).sort(
    (a, b) => TIER_STYLE[tierOf(a[0])].order - TIER_STYLE[tierOf(b[0])].order
  );
  const cheapTokens = models
    .filter(([m]) => tierOf(m) !== "max")
    .reduce((acc, [, v]) => acc + v.tokens, 0);
  const cheapPct = Math.round((cheapTokens / llm.total_tokens) * 100);
  const llmUsd = ledger?.by_category?.llm ?? 0;
  const stages = Object.entries(llm.tokens_by_stage)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4);
  const maxStage = Math.max(1, ...stages.map(([, t]) => t));

  return (
    <div className="glass rounded-xl p-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-widest text-muted-foreground">
            Token budget · live
          </p>
          <p className="text-2xl font-bold tabular-nums mt-1">
            {fmtTokens(llm.total_tokens)}
            <span className="text-sm font-normal text-muted-foreground">
              {" "}
              tokens · ${llmUsd.toFixed(3)} LLM
            </span>
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            whole drama so far: ${grand.toFixed(2)} of ${budget.toFixed(0)}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {models.map(([model, v]) => {
            const style = TIER_STYLE[tierOf(model)];
            return (
              <span
                key={model}
                className="inline-flex items-center gap-1.5 rounded-full bg-white/[0.04] px-2.5 py-1 text-xs"
              >
                <span className={cn("h-1.5 w-1.5 rounded-full", style.dot)} />
                <span className={style.text}>{model}</span>
                <span className="tabular-nums text-muted-foreground">
                  {fmtTokens(v.tokens)}
                </span>
              </span>
            );
          })}
        </div>
      </div>

      {cheapPct > 0 && (
        <p className="mt-3 text-xs text-muted-foreground">
          <span className="text-foreground font-medium">{cheapPct}%</span> of
          tokens ran on cheap tiers. Qwen Max only writes; flash and plus do
          the structuring and checking.
        </p>
      )}

      {/* the media models this drama has actually consumed, in native units */}
      {ledger?.media_models && Object.keys(ledger.media_models).length > 0 && (
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t hairline pt-3">
          {(["video", "image", "tts"] as const).flatMap((cat) =>
            Object.entries(ledger.media_models?.[cat] ?? {})
              .sort((a, b) => b[1].usd - a[1].usd)
              .map(([model, v]) => (
                <span
                  key={`${cat}-${model}`}
                  className="inline-flex items-baseline gap-1.5 text-[11px]"
                >
                  <span className="font-mono text-muted-foreground">{model}</span>
                  <span className="tabular-nums text-foreground/80">
                    {cat === "video"
                      ? `${Math.round(v.qty)}s`
                      : cat === "image"
                        ? `${Math.round(v.qty)} img`
                        : `${fmtTokens(v.qty)} ch`}
                  </span>
                  <span className="tabular-nums text-muted-foreground">
                    ${v.usd.toFixed(2)}
                  </span>
                </span>
              ))
          )}
        </div>
      )}

      {stages.length > 0 && (
        <div className="mt-3 grid gap-1.5 sm:grid-cols-2">
          {stages.map(([stage, tokens]) => (
            <div key={stage} className="flex items-center gap-2 text-xs">
              <span className="w-24 shrink-0 text-muted-foreground">
                {STAGE_LABELS[stage] ?? stage}
              </span>
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-secondary">
                <div
                  className="h-full rounded-full bg-primary/70"
                  style={{ width: `${(tokens / maxStage) * 100}%` }}
                />
              </div>
              <span className="w-12 shrink-0 text-right tabular-nums">
                {fmtTokens(tokens)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
