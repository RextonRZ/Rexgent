"use client";

import { useState } from "react";
import { ShotCard } from "./ShotCard";
import type { SceneShots } from "@/hooks/useStoryboard";

export function SceneSection({ scene }: { scene: SceneShots }) {
  const [open, setOpen] = useState(true);

  return (
    <div className="rounded-xl border border-border bg-card">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-left"
      >
        <span className="text-sm font-semibold">
          Scene {scene.scene_number}
          {scene.heading && (
            <span className="font-normal text-muted-foreground">
              {" "}
              — {scene.heading}
            </span>
          )}
        </span>
        <span className="flex items-center gap-2 text-xs text-muted-foreground shrink-0">
          {scene.shots.length} shot{scene.shots.length !== 1 ? "s" : ""}
          <span className="text-[10px]">{open ? "▾" : "▸"}</span>
        </span>
      </button>
      {open && (
        <div className="border-t border-border px-4 py-4 space-y-3">
          {scene.shots.length === 0 ? (
            <p className="text-sm text-muted-foreground">No shots.</p>
          ) : (
            scene.shots.map((shot) => <ShotCard key={shot.id} shot={shot} />)
          )}
        </div>
      )}
    </div>
  );
}
