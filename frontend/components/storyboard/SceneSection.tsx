"use client";

import { useState } from "react";
import { Trash2, Lightbulb, Palette } from "lucide-react";
import { ShotCard } from "./ShotCard";
import { ZoomableImage } from "@/components/shared/Lightbox";
import { SettingChip } from "@/components/script/BeatSheet";
import { parseSceneHeading } from "@/lib/sceneHeading";
import { useDeleteScene } from "@/hooks/useStoryboard";
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
  const deleteScene = useDeleteScene();
  // lighting + colour_mood are one scene-wide look (identical on every shot),
  // so we show them ONCE here instead of repeating them on each ShotCard.
  const look = scene.shots.find((s) => s.lighting || s.colour_mood);

  const handleDelete = () => {
    const shots = scene.shots.length;
    const what =
      shots > 0
        ? `scene ${scene.scene_number} and its ${shots} shot${shots !== 1 ? "s" : ""}`
        : `scene ${scene.scene_number}`;
    if (
      window.confirm(
        `Delete ${what}? Its synthesized voice lines are removed too. This can't be undone.`
      )
    ) {
      deleteScene.mutate(scene.id);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-card">
      {/* header: title and shot count are both collapse toggles with the
          delete control between them (a button can't legally nest inside a
          button, so the row is three siblings) */}
      <div className="group flex items-center">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex-1 min-w-0 flex items-center pl-5 pr-2 py-3.5 text-left"
        >
          <span className="flex min-w-0 items-center gap-2 text-sm font-semibold">
            <span className="shrink-0">Scene {scene.scene_number}</span>
            {scene.heading && (
              <>
                <SettingChip heading={scene.heading} />
                <span className="truncate font-normal text-muted-foreground">
                  {parseSceneHeading(scene.heading).text}
                </span>
              </>
            )}
          </span>
        </button>
        <button
          onClick={handleDelete}
          disabled={deleteScene.isPending}
          title="Delete scene"
          className="h-7 w-7 shrink-0 rounded-md text-muted-foreground opacity-0 group-hover:opacity-100 focus-visible:opacity-100 hover:text-bad hover:bg-bad/10 flex items-center justify-center disabled:opacity-50 transition-opacity"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-2 pl-2 pr-5 py-3.5 text-xs text-muted-foreground shrink-0"
        >
          {scene.shots.length} shot{scene.shots.length !== 1 ? "s" : ""}
          <span
            className={`text-[10px] transition-transform duration-200 ${
              open ? "rotate-90" : ""
            }`}
          >
            ▸
          </span>
        </button>
      </div>
      {/* animated collapse: children stay mounted, height eases via grid-rows */}
      <div
        className={`grid transition-all duration-300 ease-in-out ${
          open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
        }`}
      >
        <div className="overflow-hidden">
          <div className="border-t border-border px-5 py-4">
            <div className="flex flex-col md:flex-row gap-4">
            {/* the scene's location plate anchors the scene on the left */}
            {location && (
              <div className="md:w-44 shrink-0">
                <div className="rounded-lg overflow-hidden border hairline bg-background/40">
                  {location.url ? (
                    <ZoomableImage
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
              {/* the set dresser's contract: these props render identically in
                  every shot; state changes persist (a broken prop stays broken) */}
              {(scene.set_items?.length ?? 0) > 0 && (
                <div className="rounded-lg border hairline bg-background/40 px-3 py-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span
                      className="text-[10px] uppercase tracking-widest text-zinc-400 mr-0.5"
                      title="The set dresser's contract: these props render identically in every shot of the scene"
                    >
                      Set
                    </span>
                    {scene.set_items!.map((item) => (
                      <span
                        key={item}
                        className="rounded-full bg-white/[0.04] px-2 py-0.5 text-[11px] text-muted-foreground"
                      >
                        {item}
                      </span>
                    ))}
                  </div>
                  {(scene.state_changes?.length ?? 0) > 0 && (
                    <div className="mt-1.5 space-y-0.5">
                      {scene.state_changes!.map((c, i) => (
                        <p
                          key={i}
                          className="text-[11px] text-sky-300/90"
                          title="A deliberate set change the story causes — later shots render the changed state, never the original"
                        >
                          ↻ set change · from shot {c.from_shot}: {c.state}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {/* the scene's look, once: the lighting + colour treatment every
                  shot in the scene shares (was repeated on every shot card) */}
              {look && (look.lighting || look.colour_mood) && (
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border hairline bg-background/40 px-3 py-2 text-[11px] text-muted-foreground">
                  <span
                    className="text-[10px] uppercase tracking-widest text-zinc-400 mr-0.5"
                    title="The scene's look: one lighting and colour treatment carried across every shot"
                  >
                    Look
                  </span>
                  {look.lighting && (
                    <span className="inline-flex items-center gap-1">
                      <Lightbulb className="h-3 w-3 opacity-70" />
                      {look.lighting.toLowerCase().replace(/_/g, " ")}
                    </span>
                  )}
                  {look.colour_mood && (
                    <span className="inline-flex items-center gap-1">
                      <Palette className="h-3 w-3 opacity-70" />
                      {look.colour_mood.toLowerCase()}
                    </span>
                  )}
                </div>
              )}
              {scene.shots.length === 0 ? (
                <p className="text-sm text-muted-foreground">No shots.</p>
              ) : (
                scene.shots.map((shot) => <ShotCard key={shot.id} shot={shot} />)
              )}
            </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
