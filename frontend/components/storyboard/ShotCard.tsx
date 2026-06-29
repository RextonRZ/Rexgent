"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ShotEditor } from "./ShotEditor";
import type { Shot } from "@/lib/types";

export function ShotCard({ shot }: { shot: Shot }) {
  const [editing, setEditing] = useState(false);

  if (editing) {
    return <ShotEditor shot={shot} onClose={() => setEditing(false)} />;
  }

  const isWan = shot.quality_tier === "wan";

  return (
    <Card className="border-l-2" style={{ borderLeftColor: isWan ? "hsl(38 92% 60%)" : "hsl(199 89% 60%)" }}>
      <CardContent className="pt-4 space-y-2 text-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="outline">Shot {shot.number}</Badge>
            {shot.shot_type && <Badge variant="secondary">{shot.shot_type}</Badge>}
            {shot.camera_movement && (
              <Badge variant="secondary">{shot.camera_movement}</Badge>
            )}
            {shot.quality_tier && (
              <span
                className={
                  isWan
                    ? "inline-flex items-center gap-1 rounded-full bg-wan/15 text-wan px-2 py-0.5 text-[11px] font-medium"
                    : "inline-flex items-center gap-1 rounded-full bg-hh/15 text-hh px-2 py-0.5 text-[11px] font-medium"
                }
              >
                {isWan ? "Wan 2.7" : "HappyHorse"}
              </span>
            )}
          </div>
          <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
            Edit
          </Button>
        </div>
        {shot.action && <p>{shot.action}</p>}
        {shot.dialogue && (
          <p className="italic text-muted-foreground">&ldquo;{shot.dialogue}&rdquo;</p>
        )}
        <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
          {shot.lighting && <span>💡 {shot.lighting}</span>}
          {shot.colour_mood && <span>🎨 {shot.colour_mood}</span>}
          <span>⏱ {shot.estimated_duration_seconds}s</span>
          {shot.characters_in_frame && shot.characters_in_frame.length > 0 && (
            <span>👥 {shot.characters_in_frame.join(", ")}</span>
          )}
        </div>
        {shot.emotional_beat && (
          <p className="text-xs text-primary">Beat: {shot.emotional_beat}</p>
        )}
      </CardContent>
    </Card>
  );
}
