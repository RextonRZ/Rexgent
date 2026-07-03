"use client";

import { useState } from "react";
import { Lightbulb, Palette, Clock, Users, Pencil, Trash2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { ShotEditor } from "./ShotEditor";
import { useDeleteShot } from "@/hooks/useStoryboard";
import type { Shot } from "@/lib/types";

function Meta({
  icon: Icon,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <span className="inline-flex items-center gap-1">
      <Icon className="h-3 w-3 opacity-70" />
      {children}
    </span>
  );
}

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

  const isWan = shot.quality_tier === "wan";

  return (
    <Card className="group">
      <CardContent className="px-5 py-1.5 space-y-3 text-sm">
        {/* header: shot id + technicals left, model + hover actions right */}
        <div className="flex items-start justify-between gap-2">
          <p className="text-xs flex items-center gap-2">
            <span className="rounded bg-primary/15 text-primary px-1.5 py-0.5 font-semibold">
              Shot {shot.number}
            </span>
            {technicals && (
              <span className="text-muted-foreground">{technicals}</span>
            )}
          </p>
          <div className="flex items-center gap-1.5 shrink-0">
            <div className="flex opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
              <button
                onClick={() => setEditing(true)}
                title="Edit shot"
                className="h-7 w-7 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary flex items-center justify-center"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={handleDelete}
                disabled={deleteShot.isPending}
                title="Delete shot"
                className="h-7 w-7 rounded-md text-muted-foreground hover:text-bad hover:bg-bad/10 flex items-center justify-center disabled:opacity-50"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
            {shot.quality_tier && (
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                  isWan ? "bg-wan/15 text-wan" : "bg-hh/15 text-hh"
                }`}
              >
                {isWan ? "Wan 2.7" : "HappyHorse"}
              </span>
            )}
          </div>
        </div>

        {/* the description is the hero */}
        {shot.action && <p className="leading-relaxed">{shot.action}</p>}
        {shot.dialogue && (
          <p className="border-l-2 border-primary/40 pl-3 py-0.5 text-xs italic text-muted-foreground">
            &ldquo;{shot.dialogue}&rdquo;
          </p>
        )}

        {/* one quiet metadata row */}
        <div className="flex items-center gap-3 pt-1 pb-1 text-[11px] text-muted-foreground flex-wrap">
          {shot.lighting && (
            <Meta icon={Lightbulb}>
              {shot.lighting.toLowerCase().replace(/_/g, " ")}
            </Meta>
          )}
          {shot.colour_mood && (
            <Meta icon={Palette}>{shot.colour_mood.toLowerCase()}</Meta>
          )}
          <Meta icon={Clock}>{shot.estimated_duration_seconds}s</Meta>
          {shot.characters_in_frame && shot.characters_in_frame.length > 0 && (
            <Meta icon={Users}>{shot.characters_in_frame.join(", ")}</Meta>
          )}
          {shot.emotional_beat && (
            <span className="ml-auto rounded bg-primary/10 text-primary/90 px-1.5 py-0.5 text-[10px]">
              Beat · {shot.emotional_beat}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
