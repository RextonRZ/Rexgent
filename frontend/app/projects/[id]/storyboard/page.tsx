"use client";

import { Button } from "@/components/ui/button";
import { StoryboardView } from "@/components/storyboard/StoryboardView";
import {
  useStoryboard,
  useGenerateStoryboard,
} from "@/hooks/useStoryboard";

export default function StoryboardPage({
  params,
}: {
  params: { id: string };
}) {
  const { data, isLoading } = useStoryboard(params.id);
  const generateStoryboard = useGenerateStoryboard();

  const scenes = data?.scenes || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Storyboard</h1>
        <Button
          onClick={() => generateStoryboard.mutate(params.id)}
          disabled={generateStoryboard.isPending}
        >
          {generateStoryboard.isPending
            ? "Generating with Qwen-Max..."
            : "Generate Storyboard"}
        </Button>
      </div>
      {generateStoryboard.isError && (
        <p className="text-sm text-destructive">
          Error: {(generateStoryboard.error as Error).message}
        </p>
      )}
      {isLoading ? (
        <p className="text-muted-foreground">Loading storyboard...</p>
      ) : (
        <StoryboardView scenes={scenes} />
      )}
    </div>
  );
}
