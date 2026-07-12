"use client";

import { useState } from "react";
import type { SceneShots } from "@/hooks/useStoryboard";
import type { GeneratedClip } from "@/lib/types";
import { ClipBadge } from "@/components/budget/ClipBadge";
import { LoadingVideo } from "@/components/shared/LoadingVideo";

function TakeTile({
  clip,
  label,
  added,
  selected,
  onSelect,
  onAdd,
  onEdit,
}: {
  clip: GeneratedClip;
  label: string;
  added: boolean;
  selected: boolean;
  onSelect: () => void;
  onAdd: () => void;
  onEdit: () => void;
}) {
  return (
    <div className="space-y-1">
      <div
        className={`relative cursor-pointer rounded-md ${
          selected ? "ring-2 ring-primary" : ""
        }`}
        onClick={onSelect}
        title="Click to select, then the pen to AI-edit"
      >
        <LoadingVideo
          src={`${clip.url}#t=0.1`}
          muted
          loop
          playsInline
          preload="metadata"
          onMouseEnter={(e) => e.currentTarget.play().catch(() => {})}
          onMouseLeave={(e) => e.currentTarget.pause()}
          fitPosition="50% 22%"
          className="aspect-video w-full rounded-md border hairline bg-black"
        />
        <span className="absolute top-1 left-1 rounded bg-black/60 px-1.5 py-0.5 text-[10px] text-white/90">
          {label}
        </span>
        <span className="absolute top-1 right-1">
          <ClipBadge
            continuityScore={clip.consistency_score}
            costUsd={clip.cost_usd}
          />
        </span>
        {selected && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onEdit();
            }}
            title="AI-edit this take"
            className="absolute bottom-1.5 right-1.5 h-8 w-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center shadow-lg ring-2 ring-background hover:scale-110 transition-transform"
          >
            ✏️
          </button>
        )}
      </div>
      <button
        disabled={added}
        onClick={onAdd}
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
}

/** Right rail: scenes → shots (with description) → every generated take, plus
 *  takes from previous storyboards ("Earlier takes") so old videos stay usable. */
export function ShotLibrary({
  scenes,
  clipsByShot,
  orphans = [],
  inTimeline,
  onAdd,
  onEdit,
}: {
  scenes: SceneShots[];
  clipsByShot: Record<string, GeneratedClip[]>;
  orphans?: GeneratedClip[]; // clips whose shot no longer exists
  inTimeline: Set<string>; // clipIds currently on the timeline
  onAdd: (clip: GeneratedClip) => void;
  onEdit: (clip: GeneratedClip) => void; // open the AI-edit modal for a take
}) {
  const [selectedClipId, setSelectedClipId] = useState<string | null>(null);
  const multiEpisode = new Set(scenes.map((s) => s.episode ?? 1)).size > 1;

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
              {multiEpisode ? `EP ${scene.episode ?? 1} · ` : ""}
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
                    takes.map((clip, i) => (
                      <TakeTile
                        key={clip.id}
                        clip={clip}
                        label={`Take ${i + 1}`}
                        added={inTimeline.has(clip.id)}
                        selected={selectedClipId === clip.id}
                        onSelect={() => setSelectedClipId(clip.id)}
                        onAdd={() => onAdd(clip)}
                        onEdit={() => onEdit(clip)}
                      />
                    ))
                  )}
                </div>
              );
            })}
          </div>
        ))}

        {orphans.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold text-muted-foreground">
              Earlier takes
              <span className="ml-1 font-normal text-[11px]">
                — from previous storyboards
              </span>
            </p>
            <div className="rounded-lg border hairline bg-background/40 p-2.5 space-y-2">
              {orphans.map((clip, i) => (
                <TakeTile
                  key={clip.id}
                  clip={clip}
                  label={`Earlier ${i + 1}`}
                  added={inTimeline.has(clip.id)}
                  selected={selectedClipId === clip.id}
                  onSelect={() => setSelectedClipId(clip.id)}
                  onAdd={() => onAdd(clip)}
                  onEdit={() => onEdit(clip)}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
