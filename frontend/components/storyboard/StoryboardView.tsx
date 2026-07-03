"use client";

import { SceneSection, type SceneLocation } from "./SceneSection";
import type { SceneShots } from "@/hooks/useStoryboard";

export function StoryboardView({
  scenes,
  locationByScene,
}: {
  scenes: SceneShots[];
  locationByScene?: Record<number, SceneLocation>;
}) {
  if (scenes.length === 0 || scenes.every((s) => s.shots.length === 0)) {
    return (
      <p className="text-center text-muted-foreground py-8">
        No storyboard yet. Click &ldquo;Generate Storyboard&rdquo; to break the
        script into shots.
      </p>
    );
  }

  // Consecutive single-shot scenes pair up two per row; bigger scenes go full width.
  const blocks: SceneShots[][] = [];
  let run: SceneShots[] = [];
  for (const s of scenes) {
    if (s.shots.length === 1) {
      run.push(s);
    } else {
      if (run.length) {
        blocks.push(run);
        run = [];
      }
      blocks.push([s]);
    }
  }
  if (run.length) blocks.push(run);

  const renderScene = (scene: SceneShots) => (
    <SceneSection
      key={scene.scene_number}
      scene={scene}
      location={locationByScene?.[scene.scene_number]}
    />
  );

  return (
    <div className="space-y-4">
      {blocks.map((block, i) =>
        block.length > 1 ? (
          <div key={`pair-${i}`} className="grid gap-4 xl:grid-cols-2 items-start">
            {block.map(renderScene)}
          </div>
        ) : (
          renderScene(block[0])
        )
      )}
    </div>
  );
}
