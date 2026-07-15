"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { SpendConfirm, type SpendRequest, type SpendItem } from "@/components/shared/SpendConfirm";
import { useProject } from "@/hooks/useProjects";
import { useStartGeneration } from "@/hooks/useGeneration";
import { useCalculateBudget, type BudgetResult } from "@/hooks/useBudget";
import { useGenerationStore } from "@/stores/generationStore";
import { errText } from "@/lib/errText";

export function GenerationLauncher({ projectId }: { projectId: string }) {
  const startGeneration = useStartGeneration();
  const calcBudget = useCalculateBudget();
  const { data: project } = useProject(projectId);
  const [spend, setSpend] = useState<SpendRequest | null>(null);
  const reset = useGenerationStore((s) => s.reset);
  const jobComplete = useGenerationStore((s) => s.jobComplete);

  const cap = project?.credit_budget ?? 40;

  const run = () => {
    reset();
    startGeneration.mutate(projectId);
  };

  /** The receipt from the Producer's REAL fitted plan. Under wan_primary the
   * shots split by MODEL (Wan visuals, HappyHorse characters); otherwise by
   * quality level (full / fast). */
  const receipt = (b: BudgetResult): SpendRequest => {
    const tierCost = (tiers: string[]) =>
      b.scored_shots
        .filter((s) => tiers.includes(s.quality_tier))
        .reduce((sum, s) => sum + (s.estimated_cost_usd || 0), 0);
    const count = (tiers: string[]) =>
      b.scored_shots.filter((s) => tiers.includes(s.quality_tier)).length;
    const deferred = b.deferred_shots ?? 0;
    const wanPrimary = Boolean(b.wan_shots || b.happyhorse_shots);
    const breakdown: SpendItem[] = [];
    if (wanPrimary) {
      const wanCount = count(["wan"]);
      const hhCount = count(["happyhorse"]);
      if (wanCount > 0)
        breakdown.push({
          label: `Wan shots × ${wanCount}`,
          detail: "the silent visual shots: continuity, scenery, action",
          amount: tierCost(["wan"]),
        });
      if (hhCount > 0)
        breakdown.push({
          label: `HappyHorse shots × ${hhCount}`,
          detail: "the character shots that talk or lock a new face",
          amount: tierCost(["happyhorse"]),
        });
    } else {
      const fullCount = count(["happyhorse", "wan"]);
      const fastCount = count(["happyhorse_fast"]);
      if (fullCount > 0)
        breakdown.push({
          label: `Full-quality shots × ${fullCount}`,
          detail: "the hook and the shots that carry the story, full pass at 1080P",
          amount: tierCost(["happyhorse", "wan"]),
        });
      if (fastCount > 0)
        breakdown.push({
          label: `Fast-pass shots × ${fastCount}`,
          detail: "supporting shots on a lighter, cheaper pass",
          amount: tierCost(["happyhorse_fast"]),
        });
    }
    if (deferred > 0)
      breakdown.push({
        label: `Deferred shots × ${deferred}`,
        detail: "held back to fit your cap, render them later by raising it",
        amount: 0,
      });
    return {
      title: "Start video generation",
      costLine: wanPrimary
        ? `The Producer fitted the plan under your $${cap.toFixed(0)} cap. Each shot below is priced by the model that renders it.`
        : `The Producer fitted the plan under your $${cap.toFixed(0)} cap. Every shot below is priced by its quality level.`,
      note: "Flagged takes can be fixed individually afterwards instead of re-running everything.",
      confirmLabel: "Start generation",
      breakdown,
      run,
    };
  };

  const handleStart = () =>
    calcBudget.mutate(projectId, {
      onSuccess: (b) => setSpend(receipt(b)),
      // pricing failed — still confirm, just without the itemized plan
      onError: () =>
        setSpend({
          title: "Start video generation",
          costLine: `This is the paid step: every planned shot renders on real credit, fitted under your $${cap.toFixed(0)} cap.`,
          note: "The Producer already trimmed the plan to the cap. Flagged takes can be fixed individually afterwards.",
          confirmLabel: "Start generation",
          run,
        }),
    });

  return (
    <div className="glass rounded-xl p-5 flex items-center justify-between gap-4 flex-wrap">
      <div className="space-y-1">
        <h2 className="font-semibold">Generate video</h2>
        <p className="text-sm text-muted-foreground max-w-md">
          Every shot renders on our video model, verified against each
          character&apos;s locked identity, and self-corrected on failure.
        </p>
        {jobComplete && (
          <p className="text-sm text-ok font-medium">
            ✓ Generation complete — review and refine in the Edit step.
          </p>
        )}
        {startGeneration.isError && (
          <p className="text-sm text-bad">
            {errText(startGeneration.error)}
          </p>
        )}
      </div>
      <Button
        onClick={handleStart}
        disabled={startGeneration.isPending || calcBudget.isPending}
        size="lg"
        className="glow shrink-0"
      >
        {startGeneration.isPending
          ? "Starting…"
          : calcBudget.isPending
          ? "Pricing the plan…"
          : "▶ Start generation"}
      </Button>
      <SpendConfirm request={spend} onClose={() => setSpend(null)} />
    </div>
  );
}
