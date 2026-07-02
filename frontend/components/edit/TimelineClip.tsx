"use client";

import { cn } from "@/lib/utils";
import type { GeneratedClip } from "@/lib/types";

const STATUS_RING: Record<string, string> = {
  APPROVED: "ring-ok/60",
  NEEDS_REVIEW: "ring-warn/60",
  FAILED: "ring-bad/60",
  PENDING_REVIEW: "ring-hh/60",
};

export function TimelineClip({
  clip,
  selected,
  onClick,
}: {
  clip: GeneratedClip;
  selected: boolean;
  onClick: () => void;
}) {
  const isWan = clip.model_used === "wan";
  const match =
    clip.consistency_score != null
      ? Math.round(clip.consistency_score)
      : null;

  return (
    <button
      onClick={onClick}
      className={cn(
        "shrink-0 w-40 rounded-lg overflow-hidden bg-card border hairline ring-1 ring-inset transition-all text-left",
        STATUS_RING[clip.status] || "ring-border",
        selected && "outline outline-2 outline-primary"
      )}
    >
      <div className="relative h-20 bg-secondary">
        {clip.url ? (
          // eslint-disable-next-line jsx-a11y/media-has-caption
          <video
            src={clip.url}
            className="h-full w-full object-cover"
            preload="metadata"
          />
        ) : (
          <div className="h-full flex items-center justify-center text-[10px] text-muted-foreground">
            no clip
          </div>
        )}
        <span
          className={cn(
            "absolute top-1 left-1 rounded px-1 text-[9px] font-bold",
            isWan ? "bg-wan/20 text-wan" : "bg-hh/20 text-hh"
          )}
        >
          {isWan ? "WAN" : "HH"}
        </span>
      </div>
      <div className="px-2 py-1.5 flex items-center justify-between text-[11px]">
        <span className="text-muted-foreground capitalize">
          {clip.status.replace("_", " ").toLowerCase()}
        </span>
        {match != null && (
          <span className={match >= 60 ? "text-ok" : "text-bad"}>{match}%</span>
        )}
      </div>
    </button>
  );
}
