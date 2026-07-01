"use client";

import type { SceneShots } from "@/hooks/useStoryboard";
import type { GeneratedClip } from "@/lib/types";

/** Right rail: scenes → shots (with description) → the generated clip. */
export function ShotLibrary({
  scenes,
  clipByShot,
  inTimeline,
  onAdd,
}: {
  scenes: SceneShots[];
  clipByShot: Record<string, GeneratedClip>;
  inTimeline: Set<string>; // clipIds currently on the timeline
  onAdd: (shotId: string) => void;
}) {
  return (
    <div className="rounded-xl border hairline bg-card h-full flex flex-col">
      <div className="px-4 py-3 border-b hairline">
        <h2 className="text-sm font-medium">Shots</h2>
        <p className="text-[11px] text-muted-foreground">
          Add any shot to the timeline
        </p>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-4 max-h-[520px]">
        {scenes.map((scene) => (
          <div key={scene.scene_number} className="space-y-2">
            <p className="text-xs font-semibold text-primary/80">
              Scene {scene.scene_number}
              {scene.heading ? ` · ${scene.heading}` : ""}
            </p>
            {scene.shots.map((shot) => {
              const clip = clipByShot[shot.id];
              const added = clip ? inTimeline.has(clip.id) : false;
              return (
                <div
                  key={shot.id}
                  className="rounded-lg border hairline bg-background/40 p-2.5 space-y-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-xs font-medium">
                        Shot {shot.number}
                        {shot.shot_type ? ` · ${shot.shot_type}` : ""}
                      </p>
                      <p className="text-[11px] text-muted-foreground line-clamp-2 mt-0.5">
                        {shot.action || "—"}
                      </p>
                    </div>
                  </div>

                  {clip?.url ? (
                    <video
                      src={clip.url}
                      muted
                      loop
                      playsInline
                      preload="none"
                      onMouseEnter={(e) => e.currentTarget.play().catch(() => {})}
                      onMouseLeave={(e) => e.currentTarget.pause()}
                      className="aspect-video w-full rounded-md object-cover border hairline"
                    />
                  ) : (
                    <div className="aspect-video w-full rounded-md border border-dashed border-border flex items-center justify-center text-[11px] text-muted-foreground">
                      no clip generated
                    </div>
                  )}

                  <button
                    disabled={!clip?.url || added}
                    onClick={() => onAdd(shot.id)}
                    className={`w-full rounded-md px-2 py-1 text-[11px] font-medium transition-colors ${
                      !clip?.url
                        ? "bg-muted text-muted-foreground cursor-not-allowed"
                        : added
                        ? "bg-ok/15 text-ok cursor-default"
                        : "bg-primary/15 text-primary hover:bg-primary/25"
                    }`}
                  >
                    {!clip?.url
                      ? "unavailable"
                      : added
                      ? "✓ on timeline"
                      : "+ add to timeline"}
                  </button>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
