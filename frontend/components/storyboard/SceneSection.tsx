"use client";

import { useState } from "react";
import { ShotCard } from "./ShotCard";
import type { SceneShots } from "@/hooks/useStoryboard";

export function SceneSection({ scene }: { scene: SceneShots }) {
  const [open, setOpen] = useState(true);

  return (
    <div className="border rounded-lg">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-left"
      >
        <span className="font-semibold">
          Scene {scene.scene_number}
          {scene.heading ? ` — ${scene.heading}` : ""}
        </span>
        <span className="text-muted-foreground text-sm">
          {scene.shots.length} shot{scene.shots.length !== 1 ? "s" : ""}{" "}
          {open ? "▲" : "▼"}
        </span>
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-3">
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
