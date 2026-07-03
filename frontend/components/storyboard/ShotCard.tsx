"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { ShotEditor } from "./ShotEditor";
import { useDeleteShot } from "@/hooks/useStoryboard";
import type { Shot } from "@/lib/types";

export function ShotCard({ shot }: { shot: Shot }) {
  const [editing, setEditing] = useState(false);
  const deleteShot = useDeleteShot();

  if (editing) {
    return <ShotEditor shot={shot} onClose={() => setEditing(false)} />;
  }

  const handleDelete = () => {
    if (window.confirm(`Delete shot ${shot.number}? This can't be undone.`)) {
      deleteShot.mutate(shot.id);
    }
  };

  const technicals = [
    shot.shot_type,
    shot.camera_movement?.toLowerCase().replace(/_/g, " "),
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <Card className="group">
      <CardContent className="pt-4 space-y-2.5 text-sm">
        {/* header: shot id + technicals left, model + hover actions right */}
        <div className="flex items-start justify-between gap-2">
          <p className="text-xs font-semibold">
            Shot {shot.number}
            {technicals && (
              <span className="ml-2 font-normal text-muted-foreground">
                {technicals}
              </span>
            )}
          </p>
          <div className="flex items-center gap-1.5 shrink-0">
            {shot.quality_tier && (
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                {shot.quality_tier === "wan" ? "Wan 2.7" : "HappyHorse"}
              </span>
            )}
            <div className="flex opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
              <button
                onClick={() => setEditing(true)}
                title="Edit shot"
                className="h-7 w-7 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary flex items-center justify-center text-xs"
              >
                ✎
              </button>
              <button
                onClick={handleDelete}
                disabled={deleteShot.isPending}
                title="Delete shot"
                className="h-7 w-7 rounded-md text-muted-foreground hover:text-bad hover:bg-bad/10 flex items-center justify-center text-xs disabled:opacity-50"
              >
                🗑
              </button>
            </div>
          </div>
        </div>

        {/* the description is the hero */}
        {shot.action && <p className="leading-relaxed">{shot.action}</p>}
        {shot.dialogue && (
          <p className="border-l-2 border-border pl-3 text-xs italic text-muted-foreground">
            &ldquo;{shot.dialogue}&rdquo;
          </p>
        )}

        {/* one quiet metadata row */}
        <div className="flex items-center gap-3 pt-0.5 text-[11px] text-muted-foreground flex-wrap">
          {shot.lighting && <span>💡 {shot.lighting}</span>}
          {shot.colour_mood && <span>🎨 {shot.colour_mood}</span>}
          <span>⏱ {shot.estimated_duration_seconds}s</span>
          {shot.characters_in_frame && shot.characters_in_frame.length > 0 && (
            <span>👥 {shot.characters_in_frame.join(", ")}</span>
          )}
          {shot.emotional_beat && (
            <span className="ml-auto rounded bg-secondary px-1.5 py-0.5 text-[10px]">
              Beat · {shot.emotional_beat}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
