"use client";

import { ConsistencyBadge } from "./ConsistencyBadge";
import { cn } from "@/lib/utils";
import type { ClipProgress } from "@/stores/generationStore";

export function ClipProgressCard({ clip }: { clip: ClipProgress }) {
  const matchPct =
    clip.consistency_score != null
      ? Math.round(clip.consistency_score * 100)
      : null;
  const isWan = clip.model === "wan";

  return (
    <div className="rounded-xl border hairline bg-card overflow-hidden">
      <div className="relative aspect-video bg-secondary">
        {clip.clip_url ? (
          // eslint-disable-next-line jsx-a11y/media-has-caption
          <video
            src={clip.clip_url}
            className="h-full w-full object-cover"
            controls
            preload="metadata"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs text-muted-foreground">
              {clip.status === "GENERATING" ? "rendering…" : "queued"}
            </span>
          </div>
        )}
        {/* model badge */}
        {clip.model && (
          <span
            className={cn(
              "absolute top-2 right-2 rounded-md px-1.5 py-0.5 text-[10px] font-bold",
              isWan ? "bg-wan/20 text-wan" : "bg-hh/20 text-hh"
            )}
          >
            {isWan ? "WAN 2.7" : "HAPPYHORSE"}
          </span>
        )}
        {/* identity verification overlay */}
        {matchPct != null && (
          <span className="absolute bottom-2 left-2 rounded-md bg-black/60 backdrop-blur px-1.5 py-0.5 text-[10px] font-semibold">
            <span className="text-muted-foreground">ID</span>{" "}
            <span className={matchPct >= 60 ? "text-ok" : "text-bad"}>
              {matchPct}%
            </span>
          </span>
        )}
      </div>

      <div className="p-3 space-y-2">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[11px] text-muted-foreground">
            {clip.shot_id.slice(0, 8)}
          </span>
          <ConsistencyBadge status={clip.status} />
        </div>
        {clip.status === "CHECKING" && clip.reason && (
          <p className="text-[11px] text-warn">
            ⟳ Retry {clip.retry_number}: {clip.reason}
          </p>
        )}
      </div>
    </div>
  );
}
