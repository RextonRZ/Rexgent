"use client";

import { Card, CardContent } from "@/components/ui/card";
import type { GeneratedClip } from "@/lib/types";

export function ClipViewer({ clip }: { clip: GeneratedClip }) {
  return (
    <Card>
      <CardContent className="pt-4 space-y-2">
        {clip.url ? (
          // eslint-disable-next-line jsx-a11y/media-has-caption
          <video src={clip.url} className="w-full rounded" controls preload="metadata" />
        ) : (
          <div className="aspect-video bg-muted rounded flex items-center justify-center text-muted-foreground">
            No clip URL
          </div>
        )}
        {clip.prompt && (
          <p className="text-xs text-muted-foreground line-clamp-2">{clip.prompt}</p>
        )}
      </CardContent>
    </Card>
  );
}
