"use client";

import { cn } from "@/lib/utils";
import type { GeneratedClip } from "@/lib/types";

const STATUS_COLOR: Record<string, string> = {
  APPROVED: "border-green-500",
  NEEDS_REVIEW: "border-orange-500",
  FAILED: "border-red-500",
  PENDING_REVIEW: "border-blue-500",
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
  return (
    <button
      onClick={onClick}
      className={cn(
        "shrink-0 w-40 border-2 rounded-lg p-2 text-left transition-colors",
        STATUS_COLOR[clip.status] || "border-muted",
        selected && "ring-2 ring-primary"
      )}
    >
      {clip.url ? (
        // eslint-disable-next-line jsx-a11y/media-has-caption
        <video src={clip.url} className="w-full h-20 object-cover rounded" preload="metadata" />
      ) : (
        <div className="w-full h-20 bg-muted rounded flex items-center justify-center text-xs text-muted-foreground">
          no clip
        </div>
      )}
      <div className="mt-1 flex items-center justify-between text-xs">
        <span className="text-muted-foreground">
          {clip.model_used === "wan" ? "Wan" : "HH"}
        </span>
        {clip.consistency_score != null && (
          <span>{(clip.consistency_score * 100).toFixed(0)}%</span>
        )}
      </div>
    </button>
  );
}
