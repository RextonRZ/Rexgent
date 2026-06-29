"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { StoryboardView } from "@/components/storyboard/StoryboardView";
import { BudgetDashboard } from "@/components/storyboard/BudgetDashboard";
import { useStoryboard, useGenerateStoryboard } from "@/hooks/useStoryboard";
import { useCalculateBudget, type BudgetResult } from "@/hooks/useBudget";

export default function StoryboardPage({
  params,
}: {
  params: { id: string };
}) {
  const { data, isLoading, refetch } = useStoryboard(params.id);
  const generateStoryboard = useGenerateStoryboard();
  const calculateBudget = useCalculateBudget();
  const [budget, setBudget] = useState<BudgetResult | null>(null);

  const scenes = data?.scenes || [];

  const handleBudget = async () => {
    const result = await calculateBudget.mutateAsync(params.id);
    setBudget(result);
    refetch();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Storyboard</h1>
          <p className="text-sm text-muted-foreground">
            Shot-by-shot breakdown and budget allocation.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={() => generateStoryboard.mutate(params.id)}
            disabled={generateStoryboard.isPending}
          >
            {generateStoryboard.isPending ? "Generating…" : "Generate storyboard"}
          </Button>
          <Button
            variant="secondary"
            onClick={handleBudget}
            disabled={calculateBudget.isPending}
          >
            {calculateBudget.isPending ? "Allocating…" : "Allocate budget"}
          </Button>
        </div>
      </div>

      {generateStoryboard.isError && (
        <p className="text-sm text-bad">
          Error: {(generateStoryboard.error as Error).message}
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          {isLoading ? (
            <p className="text-muted-foreground">Loading storyboard…</p>
          ) : (
            <StoryboardView scenes={scenes} />
          )}
        </div>
        <div>
          {budget ? (
            <BudgetDashboard budget={budget} />
          ) : (
            <div className="glass rounded-xl p-5 text-sm text-muted-foreground sticky top-20">
              Generate a storyboard, then{" "}
              <span className="text-foreground font-medium">Allocate budget</span>{" "}
              to see how the $40 voucher is spread across Wan and HappyHorse shots.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
