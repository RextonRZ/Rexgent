"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { SpendConfirm, type SpendRequest } from "@/components/shared/SpendConfirm";
import { useProject } from "@/hooks/useProjects";
import { useStartGeneration } from "@/hooks/useGeneration";
import { useGenerationStore } from "@/stores/generationStore";
import { errText } from "@/lib/errText";

export function GenerationLauncher({ projectId }: { projectId: string }) {
  const startGeneration = useStartGeneration();
  const { data: project } = useProject(projectId);
  const [spend, setSpend] = useState<SpendRequest | null>(null);
  const reset = useGenerationStore((s) => s.reset);
  const jobComplete = useGenerationStore((s) => s.jobComplete);

  const cap = project?.credit_budget ?? 40;
  const handleStart = () =>
    setSpend({
      title: "Start video generation",
      costLine: `This is the paid step: every planned shot renders on real credit, fitted under your $${cap.toFixed(0)} cap.`,
      note: "The Producer already trimmed the plan to the cap. Flagged takes can be fixed individually afterwards instead of re-running everything.",
      confirmLabel: "Start generation",
      run: () => {
        reset();
        startGeneration.mutate(projectId);
      },
    });

  return (
    <div className="glass rounded-xl p-5 flex items-center justify-between gap-4 flex-wrap">
      <div className="space-y-1">
        <h2 className="font-semibold">Generate video</h2>
        <p className="text-sm text-muted-foreground max-w-md">
          Every shot is dispatched to Wan 2.7 / HappyHorse 1.1, verified against
          each character&apos;s locked identity, and self-corrected on failure.
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
        disabled={startGeneration.isPending}
        size="lg"
        className="glow shrink-0"
      >
        {startGeneration.isPending ? "Starting…" : "▶ Start generation"}
      </Button>
      <SpendConfirm request={spend} onClose={() => setSpend(null)} />
    </div>
  );
}
