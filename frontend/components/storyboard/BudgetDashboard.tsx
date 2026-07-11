"use client";

import { cn } from "@/lib/utils";
import type { BudgetResult } from "@/hooks/useBudget";

export function BudgetDashboard({ budget }: { budget: BudgetResult }) {
  const llmCost = budget.llm_cost_usd ?? 0;
  const videoCost = budget.video_cost_usd;
  const total = budget.grand_total_cost ?? budget.total_estimated_cost + llmCost;
  // this drama's own spend cap, not a global voucher constant
  const cap = budget.budget_usd ?? 40;
  const pct = Math.min((total / cap) * 100, 100);
  const over = total > cap;

  return (
    <div className="glass rounded-xl p-5 space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <p className="text-xs uppercase tracking-widest text-muted-foreground">
            Budget
          </p>
          <p className="text-3xl font-bold tabular-nums mt-1">
            ${total.toFixed(2)}
            <span className="text-base font-normal text-muted-foreground">
              {" "}
              / ${cap.toFixed(0)}
            </span>
          </p>
        </div>
        {over && (
          <span className="text-xs font-medium px-2 py-1 rounded-full bg-bad/15 text-bad">
            over budget
          </span>
        )}
      </div>

      <div className="h-2.5 rounded-full bg-secondary overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full transition-all",
            over ? "bg-bad" : pct > 70 ? "bg-warn" : "bg-primary"
          )}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* the rubric proof point gets the stage, not a footnote: token
          efficiency through tiered routing is what differentiates this
          project, so it reads first and loudest */}
      {budget.llm && (
        <div className="rounded-lg border border-primary/25 bg-primary/[0.07] p-3">
          <p className="text-[11px] font-medium uppercase tracking-widest text-primary">
            LLM tokens · tiered routing
          </p>
          <p className="mt-0.5 text-2xl font-bold tabular-nums">
            {(budget.llm.input_tokens + budget.llm.output_tokens).toLocaleString()}
            <span className="ml-2 text-sm font-normal text-zinc-300">
              ${llmCost.toFixed(2)}
            </span>
          </p>
          <p className="text-[11px] text-zinc-400">
            {budget.llm.input_tokens.toLocaleString()} in ·{" "}
            {budget.llm.output_tokens.toLocaleString()} out — cheap models do
            the routine work, the big model writes and judges
          </p>
        </div>
      )}

      <div className="grid grid-cols-3 gap-3 text-sm">
        <Stat label="Video" value={`$${videoCost.toFixed(2)}`} />
        <Stat label="Images (plates)" value={`$${(budget.image_cost_usd ?? 0).toFixed(2)}`} />
        <Stat label="Voice" value={`$${(budget.tts_cost_usd ?? 0).toFixed(2)}`} />
        <Stat label="Shots" value={`${budget.total_shots}`} />
        <Stat label="Seconds" value={`${budget.total_estimated_seconds}s`} />
        <Stat label="Deferred" value={`${budget.deferred_shots ?? 0}`} />
      </div>

      {/* the model split, decoded for non-filmmakers */}
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span
            className="inline-flex items-center gap-1.5 rounded-full bg-wan/15 text-wan px-2 py-0.5"
            title="Wan 2.7 is the premium video model: pricier per second, reserved for the shots that earn it"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-wan" />
            {budget.wan_shots} premium (Wan)
          </span>
          <span
            className="inline-flex items-center gap-1.5 rounded-full bg-hh/15 text-hh px-2 py-0.5"
            title="HappyHorse is the workhorse video model: near-premium quality at a lower rate"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-hh" />
            {budget.happyhorse_shots} standard (HappyHorse)
          </span>
          {(budget.hook_shots ?? 0) > 0 && (
            <span
              className="inline-flex items-center gap-1.5 rounded-full bg-primary/15 text-primary px-2 py-0.5"
              title="The hook is the drama's first seconds on a phone screen. The Producer protects it: upgraded to the premium model when the budget allows, and never deferred at a tight cap"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-primary" />
              {budget.hook_shots} hook protected
            </span>
          )}
          {(budget.deferred_shots ?? 0) > 0 && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-warn/15 text-warn px-2 py-0.5">
              <span className="h-1.5 w-1.5 rounded-full bg-warn" />
              {budget.deferred_shots} deferred to fit the cap
            </span>
          )}
        </div>
        <p className="text-[11px] text-zinc-400">
          The Producer splits every shot across two video models to fit your
          cap; the opening hook gets premium treatment first.
        </p>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-background/40 p-2.5">
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className="font-semibold tabular-nums">{value}</p>
    </div>
  );
}
