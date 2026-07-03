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

  return (
    <div className="space-y-4">
      {scenes.map((scene) => (
        <SceneSection
          key={scene.scene_number}
          scene={scene}
          location={locationByScene?.[scene.scene_number]}
        />
      ))}
    </div>
  );
}
