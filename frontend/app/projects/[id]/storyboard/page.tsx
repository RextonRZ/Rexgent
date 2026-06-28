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
    refetch(); // tiers were persisted onto shots
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Storyboard</h1>
        <div className="flex gap-2">
          <Button
            onClick={() => generateStoryboard.mutate(params.id)}
            disabled={generateStoryboard.isPending}
          >
            {generateStoryboard.isPending
              ? "Generating..."
              : "Generate Storyboard"}
          </Button>
          <Button
            variant="secondary"
            onClick={handleBudget}
            disabled={calculateBudget.isPending}
          >
            {calculateBudget.isPending ? "Allocating..." : "Calculate Budget"}
          </Button>
        </div>
      </div>
      {generateStoryboard.isError && (
        <p className="text-sm text-destructive">
          Error: {(generateStoryboard.error as Error).message}
        </p>
      )}
      {budget && <BudgetDashboard budget={budget} />}
      {isLoading ? (
        <p className="text-muted-foreground">Loading storyboard...</p>
      ) : (
        <StoryboardView scenes={scenes} />
      )}
    </div>
  );
}
