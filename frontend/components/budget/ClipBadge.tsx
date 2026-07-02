"use client";

import { cn } from "@/lib/utils";

function scoreTone(score: number | null | undefined) {
  if (score == null) return "bg-secondary text-muted-foreground";
  if (score >= 70) return "bg-ok/15 text-ok";
  if (score >= 55) return "bg-warn/15 text-warn";
  return "bg-bad/15 text-bad";
}

export function ClipBadge({
  continuityScore,
  costUsd,
}: {
  continuityScore?: number | null;
  costUsd?: number | null;
}) {
  const scoreLabel =
    continuityScore == null ? "—" : `${Math.round(continuityScore)}`;

  return (
    <span className="inline-flex items-center gap-1">
      <span
        className={cn(
          "rounded-full px-1.5 py-0.5 text-[10px] font-semibold",
          scoreTone(continuityScore)
        )}
        title="Continuity score"
      >
        {scoreLabel}
      </span>
      <span
        className="rounded-full bg-black/60 px-1.5 py-0.5 text-[10px] font-semibold text-white/90 backdrop-blur"
        title="Generation cost"
      >
        ${(costUsd ?? 0).toFixed(2)}
      </span>
    </span>
  );
}
