"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import type { BudgetResult } from "@/hooks/useBudget";

const VOUCHER = 40;

export function BudgetDashboard({ budget }: { budget: BudgetResult }) {
  const llmCost = budget.llm_cost_usd ?? 0;
  const videoCost = budget.video_cost_usd;
  const total = budget.grand_total_cost ?? budget.total_estimated_cost + llmCost;
  const pct = Math.min((total / VOUCHER) * 100, 100);
  const over = total > VOUCHER;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Token Budget</span>
          <span className="text-sm font-normal">
            ${total.toFixed(2)} / ${VOUCHER.toFixed(2)}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Progress value={pct} className={over ? "[&>div]:bg-destructive" : ""} />
        <div className="grid grid-cols-3 gap-2 text-sm">
          <div>
            <p className="text-muted-foreground text-xs">LLM (Qwen-Max)</p>
            <p className="font-medium">${llmCost.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-muted-foreground text-xs">Video</p>
            <p className="font-medium">${videoCost.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-muted-foreground text-xs">Total</p>
            <p className="font-medium">${total.toFixed(2)}</p>
          </div>
        </div>
        {budget.llm && (
          <p className="text-xs text-muted-foreground">
            {budget.llm.input_tokens.toLocaleString()} in /{" "}
            {budget.llm.output_tokens.toLocaleString()} out tokens ·{" "}
            {budget.total_shots} shots · {budget.total_estimated_seconds}s video
          </p>
        )}
        <div className="flex items-center gap-2 text-xs">
          <Badge className="bg-amber-500">{budget.wan_shots} Wan</Badge>
          <Badge className="bg-slate-400">
            {budget.happyhorse_shots} HappyHorse
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          {budget.optimisation_summary}
        </p>
        {over && (
          <p className="text-sm text-destructive font-medium">
            ⚠ Projected cost exceeds available credit. Drop some shots to a
            lower tier or shorten durations.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
