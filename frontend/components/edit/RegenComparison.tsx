"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface RegenComparisonProps {
  originalUrl: string | null;
  regenUrl: string;
  regenClipId: string;
  changesMade: string[];
  onApprove: (clipId: string) => void;
  onKeepOriginal: () => void;
}

export function RegenComparison({
  originalUrl,
  regenUrl,
  regenClipId,
  changesMade,
  onApprove,
  onKeepOriginal,
}: RegenComparisonProps) {
  return (
    <Card>
      <CardContent className="pt-4 space-y-3">
        <p className="text-sm font-medium">Compare</p>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Original</p>
            {originalUrl ? (
              // eslint-disable-next-line jsx-a11y/media-has-caption
              <video src={originalUrl} className="w-full rounded" controls preload="metadata" />
            ) : (
              <div className="aspect-video bg-muted rounded" />
            )}
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Regenerated</p>
            {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
            <video src={regenUrl} className="w-full rounded" controls preload="metadata" />
          </div>
        </div>
        {changesMade.length > 0 && (
          <ul className="text-xs text-muted-foreground space-y-0.5">
            {changesMade.map((c, i) => (
              <li key={i}>• {c}</li>
            ))}
          </ul>
        )}
        <div className="flex gap-2">
          <Button size="sm" onClick={() => onApprove(regenClipId)}>
            Use Regenerated
          </Button>
          <Button size="sm" variant="outline" onClick={onKeepOriginal}>
            Keep Original
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
