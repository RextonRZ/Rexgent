"use client";

import { useState } from "react";
import { ShotCard } from "./ShotCard";
import type { SceneShots } from "@/hooks/useStoryboard";

export interface SceneLocation {
  url?: string | null;
  label: string;
}

export function SceneSection({
  scene,
  location,
}: {
  scene: SceneShots;
  location?: SceneLocation;
}) {
  const [open, setOpen] = useState(true);

  return (
    <div className="rounded-xl border border-border bg-card">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-3.5 text-left"
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
        <div className="border-t border-border px-5 py-4">
          <div className="flex flex-col md:flex-row gap-4">
            {/* the scene's location plate anchors the scene on the left */}
            {location && (
              <div className="md:w-44 shrink-0">
                <div className="rounded-lg overflow-hidden border hairline bg-background/40">
                  {location.url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={location.url}
                      alt={location.label}
                      className="aspect-square w-full object-cover"
                    />
                  ) : (
                    <div className="aspect-square w-full flex items-center justify-center text-[10px] text-muted-foreground">
                      no location plate yet
                    </div>
                  )}
                </div>
                <p className="mt-1.5 text-[11px] text-muted-foreground leading-snug">
                  {location.label}
                </p>
              </div>
            )}
            <div className="flex-1 min-w-0 space-y-3">
              {scene.shots.length === 0 ? (
                <p className="text-sm text-muted-foreground">No shots.</p>
              ) : (
                scene.shots.map((shot) => <ShotCard key={shot.id} shot={shot} />)
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
