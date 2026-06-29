"use client";

import { Card, CardContent } from "@/components/ui/card";
import { ConsistencyBadge } from "./ConsistencyBadge";
import type { ClipProgress } from "@/stores/generationStore";

export function ClipProgressCard({ clip }: { clip: ClipProgress }) {
  return (
    <Card>
      <CardContent className="pt-4 space-y-2 text-sm">
        <div className="flex items-center justify-between">
          <span className="font-mono text-xs text-muted-foreground">
            {clip.shot_id.slice(0, 8)}
          </span>
          <ConsistencyBadge status={clip.status} />
        </div>
        {clip.model && (
          <p className="text-xs">
            <span className="text-muted-foreground">Model:</span>{" "}
            {clip.model === "wan" ? "Wan 2.7" : "HappyHorse 1.1"}
          </p>
        )}
        {clip.consistency_score != null && (
          <p className="text-xs">
            <span className="text-muted-foreground">Face match:</span>{" "}
            {(clip.consistency_score * 100).toFixed(0)}%
          </p>
        )}
        {clip.status === "CHECKING" && clip.reason && (
          <p className="text-xs text-yellow-600">
            Retry {clip.retry_number}: {clip.reason}
          </p>
        )}
        {clip.clip_url && (
          // eslint-disable-next-line jsx-a11y/media-has-caption
          <video
            src={clip.clip_url}
            className="w-full rounded mt-1"
            controls
            preload="metadata"
          />
        )}
      </CardContent>
    </Card>
  );
}
