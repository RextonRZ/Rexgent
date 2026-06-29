"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useStartGeneration } from "@/hooks/useGeneration";
import { useGenerationStore } from "@/stores/generationStore";

export function GenerationLauncher({ projectId }: { projectId: string }) {
  const startGeneration = useStartGeneration();
  const reset = useGenerationStore((s) => s.reset);
  const jobComplete = useGenerationStore((s) => s.jobComplete);

  const handleStart = () => {
    reset();
    startGeneration.mutate(projectId);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Generate Video</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-sm text-muted-foreground">
          Dispatches every storyboard shot to Wan 2.7 / HappyHorse 1.1, validates
          each clip with ConsistencyGuard, and self-corrects failures.
        </p>
        <Button
          onClick={handleStart}
          disabled={startGeneration.isPending}
          className="w-full"
        >
          {startGeneration.isPending ? "Starting..." : "Start Generation"}
        </Button>
        {jobComplete && (
          <p className="text-sm text-green-600 font-medium">
            Generation complete. Head to the Edit step to review and refine.
          </p>
        )}
        {startGeneration.isError && (
          <p className="text-sm text-destructive">
            {(startGeneration.error as Error).message}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
