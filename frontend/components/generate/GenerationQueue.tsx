"use client";

import { useGenerationStore } from "@/stores/generationStore";
import { useStoryboard } from "@/hooks/useStoryboard";
import { clipStatusChip } from "@/lib/clipStatus";

export function GenerationQueue({ projectId }: { projectId: string }) {
  const clips = useGenerationStore((s) => s.clips);
  const { data } = useStoryboard(projectId);
  const scenes = data?.scenes ?? [];
  const hasAny = Object.keys(clips).length > 0;

  if (!hasAny) {
    return (
      <p className="text-center text-muted-foreground py-8">
        No clips yet. Start generation to watch progress live.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {scenes.map((scene) => {
        const shots = scene.shots.filter((sh) => clips[sh.id]);
        if (shots.length === 0) return null;
        return (
          <div key={scene.scene_number}>
            <div className="flex items-center gap-2 mb-3 text-sm">
              <span className="font-semibold">Scene {scene.scene_number}</span>
              {scene.heading && (
                <span className="text-muted-foreground">— {scene.heading}</span>
              )}
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {shots.map((shot) => {
                const clip = clips[shot.id];
                const chip = clipStatusChip(clip.status);
                const score = clip.consistency_score;
                return (
                  <div
                    key={shot.id}
                    className="rounded-xl border hairline bg-card overflow-hidden"
                  >
                    <div className="relative aspect-video bg-black">
                      {clip.clip_url ? (
                        <video
                          src={`${clip.clip_url}#t=0.1`}
                          muted
                          loop
                          playsInline
                          preload="metadata"
                          onMouseEnter={(e) => e.currentTarget.play().catch(() => {})}
                          onMouseLeave={(e) => e.currentTarget.pause()}
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <div className="h-full w-full flex items-center justify-center text-xs text-muted-foreground">
                          {clip.status === "GENERATING" || clip.status === "CHECKING"
                            ? "rendering…"
                            : clip.status.toLowerCase()}
                        </div>
                      )}
                      <span className="absolute top-2 left-2 rounded bg-black/60 px-2 py-0.5 text-[11px] font-semibold text-white">
                        Shot {shot.number}
                        {shot.shot_type ? ` · ${shot.shot_type}` : ""}
                      </span>
                      <span
                        className={`absolute top-2 right-2 rounded-full px-2 py-0.5 text-[10px] ${chip.cls}`}
                      >
                        {chip.label}
                      </span>
                      {typeof score === "number" && (
                        <span
                          className={`absolute bottom-2 left-2 text-[11px] font-bold ${
                            score >= 70 ? "text-ok" : "text-warn"
                          }`}
                        >
                          ID {score}%
                        </span>
                      )}
                    </div>
                    <div className="p-3">
                      {shot.action && (
                        <p className="text-xs text-foreground line-clamp-2">
                          {shot.action}
                        </p>
                      )}
                      {shot.dialogue && (
                        <p className="mt-1 text-[11px] italic text-primary/80 line-clamp-1">
                          “{shot.dialogue}”
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
