"use client";

import { useState } from "react";
import { Home, Trees } from "lucide-react";
import { cn } from "@/lib/utils";
import { parseSceneHeading } from "@/lib/sceneHeading";
import type { StructuredScript } from "@/lib/types";

/** "Indoor"/"Outdoor" in plain words — INT./EXT. is screenwriter jargon. */
export function SettingChip({
  heading,
  location,
}: {
  heading?: string | null;
  location?: string | null;
}) {
  const { setting } = parseSceneHeading(heading, location);
  if (!setting) return null;
  const outdoor = setting === "Outdoor";
  const Icon = outdoor ? Trees : Home;
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
        outdoor ? "bg-ok/10 text-ok" : "bg-sky-500/10 text-sky-300"
      )}
    >
      <Icon className="size-2.5" />
      {setting}
    </span>
  );
}

/** The narrative ladder, visible: logline → beats per scene, with the two
 * micro drama landmarks called out (the 3 second hook, the cliffhanger). */
export function BeatSheet({ structured }: { structured: StructuredScript }) {
  const [open, setOpen] = useState(true);
  const scenes = structured.scenes ?? [];
  if (!structured.logline && scenes.length === 0) return null;

  return (
    <div className="rounded-xl border hairline bg-card">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-left"
      >
        <span className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
          Beat sheet
        </span>
        <span
          className={cn(
            "text-[10px] text-muted-foreground transition-transform duration-200",
            open && "rotate-90"
          )}
        >
          ▸
        </span>
      </button>
      {open && (
        <div className="border-t hairline px-4 py-3 space-y-2.5">
          {structured.logline && (
            <p className="text-sm text-foreground">{structured.logline}</p>
          )}
          {scenes.length > 0 && (
            <ol className="space-y-1">
              {scenes.map((sc, i) => (
                <li key={sc.scene_number} className="flex items-baseline gap-2 text-xs">
                  <span className="w-5 shrink-0 text-right font-mono text-muted-foreground">
                    {sc.scene_number}
                  </span>
                  <SettingChip heading={sc.heading} location={sc.location} />
                  <span className="truncate text-muted-foreground">
                    {parseSceneHeading(sc.heading, sc.location).text ||
                      sc.location}
                  </span>
                  {sc.emotional_beat && (
                    <span className="shrink-0 rounded-full bg-white/[0.04] px-2 py-0.5 text-[10px] text-foreground/80">
                      {sc.emotional_beat}
                    </span>
                  )}
                  {i === 0 && (
                    <span className="shrink-0 rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-medium text-primary">
                      hook
                    </span>
                  )}
                  {i === scenes.length - 1 && scenes.length > 1 && (
                    <span className="shrink-0 rounded-full bg-warn/15 px-2 py-0.5 text-[10px] font-medium text-warn">
                      cliffhanger
                    </span>
                  )}
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}
