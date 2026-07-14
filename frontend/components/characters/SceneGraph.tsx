"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { BlockingDiagram } from "@/components/storyboard/BlockingDiagram";
import { explainFilmTerm, fullShotType } from "@/lib/filmTerms";
import { tierLabel, isFullTier } from "@/lib/qualityTier";
import type {
  GraphScene,
  GraphCharacterInfo,
} from "@/hooks/useRelationshipGraph";
import type { SceneShots } from "@/hooks/useStoryboard";

/** Horizontal scene flow: each scene is a card with its location plate and the
 *  faces of the characters in it, connected in story order. When the board
 *  exists, tapping a scene opens a right-side panel with the camera plan
 *  (top-down blocking diagram) of every shot in it. */
export function SceneGraph({
  scenes,
  characters,
  boardScenes,
}: {
  scenes: GraphScene[];
  characters: GraphCharacterInfo[];
  boardScenes?: SceneShots[];
}) {
  const [openScene, setOpenScene] = useState<number | null>(null);

  if (scenes.length === 0) {
    return (
      <p className="text-center text-muted-foreground py-8">
        No scenes to graph yet.
      </p>
    );
  }

  const faceByName = new Map(
    characters.map((c) => [c.name.toUpperCase(), c.reference_image_url])
  );
  const boardByNumber = new Map(
    (boardScenes ?? []).map((s) => [s.scene_number, s])
  );
  const open = openScene != null ? boardByNumber.get(openScene) : undefined;

  return (
    <div className="rounded-xl border hairline bg-card p-4">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">
        Scene flow
      </p>
      <p className="mt-0.5 mb-3 text-[11px] text-muted-foreground">
        {boardByNumber.size > 0
          ? "Tap a scene to open its camera plan."
          : "Board the script and each scene opens into a camera plan."}
      </p>
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {scenes.map((scene, i) => {
          const board = boardByNumber.get(scene.number);
          const clickable = !!board && board.shots.length > 0;
          const selected = openScene === scene.number;
          return (
            <div key={scene.number} className="flex items-center gap-2 shrink-0">
              <div
                onClick={
                  clickable
                    ? () =>
                        setOpenScene((o) =>
                          o === scene.number ? null : scene.number
                        )
                    : undefined
                }
                title={
                  clickable
                    ? "Tap to see each shot's camera position"
                    : undefined
                }
                className={`w-56 rounded-xl border bg-background/40 overflow-hidden transition-colors ${
                  selected ? "border-primary/60 ring-1 ring-primary/40" : "hairline"
                } ${clickable ? "cursor-pointer hover:border-primary/40" : ""}`}
              >
                <div className="relative h-24 bg-secondary/40">
                  {scene.image ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={scene.image}
                      alt={scene.heading || `Scene ${scene.number}`}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center text-[10px] text-muted-foreground">
                      no location plate yet
                    </div>
                  )}
                  <span className="absolute top-1.5 left-1.5 rounded bg-black/60 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                    Scene {scene.number}
                  </span>
                  {clickable && (
                    <span className="absolute bottom-1.5 right-1.5 rounded bg-black/60 px-1.5 py-0.5 text-[10px] text-white/90">
                      {board!.shots.length} shot{board!.shots.length !== 1 ? "s" : ""} ▸
                    </span>
                  )}
                </div>
                <div className="p-2.5 space-y-2">
                  <p className="text-[11px] font-medium line-clamp-1">
                    {scene.heading || "Untitled"}
                  </p>
                  <div className="flex items-center -space-x-1.5">
                    {(scene.characters || []).map((name) => {
                      const img = faceByName.get(String(name).toUpperCase());
                      return img ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          key={name}
                          src={img}
                          alt={name}
                          title={name}
                          className="h-7 w-7 rounded-full object-cover border-2 border-card"
                        />
                      ) : (
                        <span
                          key={name}
                          title={name}
                          className="h-7 w-7 rounded-full bg-secondary text-[9px] font-medium flex items-center justify-center border-2 border-card text-muted-foreground"
                        >
                          {String(name).slice(0, 2)}
                        </span>
                      );
                    })}
                    {(scene.characters || []).length === 0 && (
                      <span className="text-[10px] text-muted-foreground">
                        no cast listed
                      </span>
                    )}
                  </div>
                </div>
              </div>
              {i < scenes.length - 1 && (
                <span className="text-muted-foreground shrink-0">→</span>
              )}
            </div>
          );
        })}
      </div>

      {/* the camera plan drawer: every shot of the tapped scene, top down */}
      {open && (
        <div className="fixed inset-y-0 right-0 z-50 flex w-[360px] max-w-[90vw] flex-col border-l hairline bg-card shadow-2xl">
          <div className="flex items-center justify-between border-b hairline px-4 py-3">
            <div className="min-w-0">
              <p className="text-sm font-semibold">
                Scene {open.scene_number} camera plan
              </p>
              {open.heading && (
                <p className="truncate text-[11px] text-muted-foreground">
                  {open.heading}
                </p>
              )}
            </div>
            <button
              onClick={() => setOpenScene(null)}
              title="Close"
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="flex-1 space-y-4 overflow-y-auto p-4">
            {open.shots.map((shot) => {
              const isFull = isFullTier(shot.quality_tier);
              const isDeferred = shot.quality_tier === "deferred";
              return (
                <div
                  key={shot.id}
                  className="overflow-hidden rounded-lg border hairline bg-background/40"
                >
                  {/* header: number · full shot type · movement · duration */}
                  <div className="flex items-center gap-2 border-b hairline px-3 py-2 text-xs">
                    <span className="shrink-0 rounded bg-primary/15 px-1.5 py-0.5 font-semibold text-primary">
                      Shot {shot.number}
                    </span>
                    <span className="min-w-0 truncate">
                      {shot.shot_type && (
                        <span
                          className="cursor-help underline decoration-dotted decoration-white/20 underline-offset-2"
                          title={explainFilmTerm(shot.shot_type)}
                        >
                          {fullShotType(shot.shot_type)}
                        </span>
                      )}
                      {shot.camera_movement && (
                        <span className="text-muted-foreground">
                          {" "}
                          · {shot.camera_movement.toLowerCase().replace(/_/g, " ")}
                        </span>
                      )}
                    </span>
                    <span className="ml-auto shrink-0 tabular-nums text-muted-foreground">
                      {shot.estimated_duration_seconds}s
                    </span>
                  </div>

                  <div className="space-y-2 px-3 py-2.5">
                    {shot.action && (
                      <p className="text-xs leading-relaxed">{shot.action}</p>
                    )}
                    {shot.dialogue && (
                      <p className="border-l-2 border-primary/40 py-0.5 pl-2.5 text-[11px] italic text-muted-foreground">
                        &ldquo;{shot.dialogue}&rdquo;
                      </p>
                    )}
                    {shot.blocking_json?.subjects &&
                    shot.blocking_json.subjects.length > 0 ? (
                      <BlockingDiagram
                        blocking={shot.blocking_json}
                        cameraMovement={shot.camera_movement}
                        shotType={shot.shot_type}
                      />
                    ) : (
                      <p className="text-[11px] text-muted-foreground/70">
                        No camera geometry recorded for this shot.
                      </p>
                    )}
                  </div>

                  {/* footer: who is in it, the mood, and which model renders it */}
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5 border-t hairline px-3 py-2 text-[10px] text-zinc-300">
                    {(shot.characters_in_frame ?? []).length > 0 && (
                      <span className="flex items-center -space-x-1">
                        {shot.characters_in_frame!.map((name) => {
                          const img = faceByName.get(String(name).toUpperCase());
                          return img ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              key={name}
                              src={img}
                              alt={name}
                              title={name}
                              className="h-5 w-5 rounded-full border border-card object-cover"
                            />
                          ) : (
                            <span
                              key={name}
                              title={name}
                              className="flex h-5 w-5 items-center justify-center rounded-full border border-card bg-secondary text-[8px] font-medium text-muted-foreground"
                            >
                              {String(name).slice(0, 2)}
                            </span>
                          );
                        })}
                      </span>
                    )}
                    {(shot.lighting || shot.colour_mood) && (
                      <span className="text-zinc-400">
                        {[shot.lighting, shot.colour_mood]
                          .filter(Boolean)
                          .map((v) => String(v).toLowerCase().replace(/_/g, " "))
                          .join(" · ")}
                      </span>
                    )}
                    <span className="ml-auto flex items-center gap-1.5">
                      {shot.emotional_beat && (
                        <span className="rounded bg-primary/10 px-1.5 py-0.5 text-primary/90">
                          {shot.emotional_beat}
                        </span>
                      )}
                      {shot.quality_tier && (
                        <span
                          className={`rounded-full px-1.5 py-0.5 font-medium ${
                            isDeferred
                              ? "bg-warn/15 text-warn"
                              : isFull
                                ? "bg-wan/15 text-wan"
                                : "bg-hh/15 text-hh"
                          }`}
                        >
                          {tierLabel(shot.quality_tier)}
                        </span>
                      )}
                    </span>
                  </div>
                </div>
              );
            })}
            {open.shots.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No shots in this scene.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
