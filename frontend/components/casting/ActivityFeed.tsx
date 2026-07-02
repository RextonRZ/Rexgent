"use client";

import { useEffect, useRef } from "react";
import { useActivityFeed, type FeedItem } from "@/hooks/useActivityFeed";

const EVENT_LABEL: Record<string, string> = {
  "casting.started": "Casting started",
  "casting.wardrobe_plan.completed": "Wardrobe plan ready",
  "casting.plate.started": "Generating plate",
  "casting.plate.completed": "Plate completed",
  "casting.awaiting_review": "Awaiting your review",
  "casting.completed": "Casting complete",
  "job:blocked": "Job blocked",
  "job:budget_exhausted": "Budget exhausted",
  "job:completed": "Job completed",
  "generation.shot.started": "Generating shot",
  "generation.shot.completed": "Shot completed",
  "continuity.scoring.started": "Scoring continuity",
  "continuity.scoring.completed": "Continuity scored",
  "continuity.flagged": "Continuity flagged",
  "cost:updated": "Cost updated",
};

function label(item: FeedItem) {
  return EVENT_LABEL[item.event] || item.event;
}

function progressFragment(item: FeedItem) {
  const { index, total } = item.payload || {};
  if (typeof index === "number" && typeof total === "number") {
    return `Plate ${index}/${total}`;
  }
  return null;
}

function formatTime(at: number) {
  const d = new Date(at);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function ActivityFeed({ projectId }: { projectId: string }) {
  const items = useActivityFeed(projectId);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [items.length]);

  return (
    <div className="rounded-xl border hairline bg-card h-full flex flex-col">
      <div className="px-4 py-3 border-b hairline">
        <h2 className="text-sm font-medium">Activity</h2>
        <p className="text-[11px] text-muted-foreground">
          Live updates from the studio
        </p>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2 max-h-[520px]">
        {items.length === 0 ? (
          <p className="text-xs text-muted-foreground">Waiting for activity…</p>
        ) : (
          items.map((item, i) => {
            const progress = progressFragment(item);
            return (
              <div
                key={`${item.event}-${item.at}-${i}`}
                className="rounded-lg border hairline bg-background/40 px-2.5 py-2 text-xs"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{label(item)}</span>
                  <span className="text-[10px] text-muted-foreground shrink-0">
                    {formatTime(item.at)}
                  </span>
                </div>
                {progress && (
                  <p className="text-[11px] text-primary/80 mt-0.5">{progress}</p>
                )}
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
