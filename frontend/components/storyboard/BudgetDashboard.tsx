"use client";

import { cn } from "@/lib/utils";
import type { BudgetResult } from "@/hooks/useBudget";

const VOUCHER = 40;

export function BudgetDashboard({ budget }: { budget: BudgetResult }) {
  const llmCost = budget.llm_cost_usd ?? 0;
  const videoCost = budget.video_cost_usd;
  const total = budget.grand_total_cost ?? budget.total_estimated_cost + llmCost;
  const pct = Math.min((total / VOUCHER) * 100, 100);
  const over = total > VOUCHER;

  return (
    <div className="glass rounded-xl p-5 space-y-4 sticky top-20">
      <div className="flex items-end justify-between">
        <div>
          <p className="text-xs uppercase tracking-widest text-muted-foreground">
            Budget
          </p>
          <p className="text-3xl font-bold tabular-nums mt-1">
            ${total.toFixed(2)}
            <span className="text-base font-normal text-muted-foreground">
              {" "}
              / ${VOUCHER}
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

      <div className="grid grid-cols-2 gap-3 text-sm">
        <Stat label="LLM (Qwen-Max)" value={`$${llmCost.toFixed(2)}`} />
        <Stat label="Video" value={`$${videoCost.toFixed(2)}`} />
        <Stat label="Shots" value={`${budget.total_shots}`} />
        <Stat label="Seconds" value={`${budget.total_estimated_seconds}s`} />
      </div>

      <div className="flex items-center gap-2 text-xs">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-wan/15 text-wan px-2 py-0.5">
          <span className="h-1.5 w-1.5 rounded-full bg-wan" />
          {budget.wan_shots} Wan
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-hh/15 text-hh px-2 py-0.5">
          <span className="h-1.5 w-1.5 rounded-full bg-hh" />
          {budget.happyhorse_shots} HappyHorse
        </span>
      </div>

      <p className="text-xs text-muted-foreground border-t hairline pt-3">
        {budget.optimisation_summary}
      </p>

      {budget.llm && (
        <p className="text-[11px] text-muted-foreground">
          {budget.llm.input_tokens.toLocaleString()} in /{" "}
          {budget.llm.output_tokens.toLocaleString()} out tokens
        </p>
      )}
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
