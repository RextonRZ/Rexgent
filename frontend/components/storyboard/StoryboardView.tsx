"use client";

import { SceneSection, type SceneLocation } from "./SceneSection";
import type { SceneShots } from "@/hooks/useStoryboard";

/** Distinct episode numbers present on a board, in order. */
export function episodesOf(scenes: SceneShots[]): number[] {
  return Array.from(new Set(scenes.map((s) => s.episode ?? 1))).sort(
    (a, b) => a - b
  );
}

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

  const episodes = episodesOf(scenes);

  // one episode: the board reads exactly as before, no episode chrome
  if (episodes.length <= 1) {
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

  return (
    <div className="space-y-6">
      {episodes.map((ep) => {
        const epScenes = scenes.filter((s) => (s.episode ?? 1) === ep);
        const shotCount = epScenes.reduce((n, s) => n + s.shots.length, 0);
        return (
          <div key={ep} className="space-y-4">
            <div className="flex items-center gap-3">
              <span className="rounded-full bg-primary/15 px-2.5 py-0.5 text-xs font-semibold text-primary">
                Episode {ep}
              </span>
              <span className="text-[11px] text-muted-foreground">
                {epScenes.length} scene{epScenes.length !== 1 ? "s" : ""} ·{" "}
                {shotCount} shot{shotCount !== 1 ? "s" : ""}
              </span>
              <span className="h-px flex-1 bg-white/[0.07]" />
            </div>
            {epScenes.map((scene) => (
              <SceneSection
                key={scene.scene_number}
                scene={scene}
                location={locationByScene?.[scene.scene_number]}
              />
            ))}
          </div>
        );
      })}
    </div>
  );
}
