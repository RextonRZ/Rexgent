"use client";

import type { SceneShots } from "@/hooks/useStoryboard";
import type { GeneratedClip } from "@/lib/types";

function pct(score: number | null) {
  return score == null ? "—" : `${Math.round(score * 100)}%`;
}

/** Right rail: scenes → shots (with description) → every generated take. */
export function ShotLibrary({
  scenes,
  clipsByShot,
  inTimeline,
  onAdd,
}: {
  scenes: SceneShots[];
  clipsByShot: Record<string, GeneratedClip[]>;
  inTimeline: Set<string>; // clipIds currently on the timeline
  onAdd: (clip: GeneratedClip) => void;
}) {
  return (
    <div className="rounded-xl border hairline bg-card h-full flex flex-col">
      <div className="px-4 py-3 border-b hairline">
        <h2 className="text-sm font-medium">Shots &amp; takes</h2>
        <p className="text-[11px] text-muted-foreground">
          Each shot may have several takes — add any to the timeline
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
              const takes = clipsByShot[shot.id] || [];
              return (
                <div
                  key={shot.id}
                  className="rounded-lg border hairline bg-background/40 p-2.5 space-y-2"
                >
                  <div>
                    <p className="text-xs font-medium">
                      Shot {shot.number}
                      {shot.shot_type ? ` · ${shot.shot_type}` : ""}
                      {takes.length > 1 ? (
                        <span className="ml-1 text-primary/70">
                          · {takes.length} takes
                        </span>
                      ) : null}
                    </p>
                    <p className="text-[11px] text-muted-foreground line-clamp-2 mt-0.5">
                      {shot.action || "—"}
                    </p>
                  </div>

                  {takes.length === 0 ? (
                    <div className="aspect-video w-full rounded-md border border-dashed border-border flex items-center justify-center text-[11px] text-muted-foreground">
                      no clip generated
                    </div>
                  ) : (
                    takes.map((clip, i) => {
                      const added = inTimeline.has(clip.id);
                      const verified = clip.status === "APPROVED";
                      return (
                        <div key={clip.id} className="space-y-1">
                          <div className="relative">
                            <video
                              src={`${clip.url}#t=0.1`}
                              muted
                              loop
                              playsInline
                              preload="metadata"
                              onMouseEnter={(e) =>
                                e.currentTarget.play().catch(() => {})
                              }
                              onMouseLeave={(e) => e.currentTarget.pause()}
                              className="aspect-video w-full rounded-md object-cover border hairline bg-black"
                            />
                            <span className="absolute top-1 left-1 rounded bg-black/60 px-1.5 py-0.5 text-[10px] text-white/90">
                              Take {i + 1}
                            </span>
                            <span
                              className={`absolute top-1 right-1 rounded px-1.5 py-0.5 text-[10px] ${
                                verified
                                  ? "bg-ok/80 text-white"
                                  : "bg-warn/80 text-black"
                              }`}
                            >
                              ID {pct(clip.consistency_score)}
                            </span>
                          </div>
                          <button
                            disabled={added}
                            onClick={() => onAdd(clip)}
                            className={`w-full rounded-md px-2 py-1 text-[11px] font-medium transition-colors ${
                              added
                                ? "bg-ok/15 text-ok cursor-default"
                                : "bg-primary/15 text-primary hover:bg-primary/25"
                            }`}
                          >
                            {added ? "✓ on timeline" : "+ add take"}
                          </button>
                        </div>
                      );
                    })
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
