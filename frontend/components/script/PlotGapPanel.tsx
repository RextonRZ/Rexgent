"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { PlotFlag } from "@/lib/types";

interface PlotGapPanelProps {
  flags: PlotFlag[];
  onDismiss?: (flagId: string) => void;
}

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: "bg-red-500",
  MAJOR: "bg-orange-500",
  MINOR: "bg-yellow-500",
};

const FLAG_TYPE_LABELS: Record<string, string> = {
  MISSING_MOTIVATION: "Missing Motivation",
  CONTINUITY_BREAK: "Continuity Break",
  UNRESOLVED_THREAD: "Unresolved Thread",
  PACING_ISSUE: "Pacing Issue",
  CHARACTER_INCONSISTENCY: "Character Inconsistency",
};

export function PlotGapPanel({ flags, onDismiss }: PlotGapPanelProps) {
  if (flags.length === 0) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground text-center">
            No narrative issues found.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Plot Analysis</span>
          <Badge variant="outline">
            {flags.length} issue{flags.length !== 1 ? "s" : ""}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {flags.map((flag) => (
          <div key={flag.id} className="border rounded-lg p-3 space-y-2">
            <div className="flex items-center gap-2">
              <div
                className={`w-2 h-2 rounded-full ${
                  SEVERITY_COLORS[flag.severity] || "bg-gray-400"
                }`}
              />
              <span className="text-sm font-medium">
                {FLAG_TYPE_LABELS[flag.flag_type] || flag.flag_type}
              </span>
              <Badge variant="secondary" className="text-xs">
                Scene {flag.scene_number}
              </Badge>
              {flag.status !== "OPEN" && (
                <Badge variant="outline" className="text-xs">
                  {flag.status}
                </Badge>
              )}
            </div>
            <p className="text-sm">{flag.description}</p>
            {flag.evidence && (
              <p className="text-xs text-muted-foreground italic">
                &ldquo;{flag.evidence}&rdquo;
              </p>
            )}
            {flag.suggestion && (
              <p className="text-xs text-primary">
                Suggestion: {flag.suggestion}
              </p>
            )}
            {onDismiss && flag.status === "OPEN" && (
              <button
                onClick={() => onDismiss(flag.id)}
                className="text-xs text-muted-foreground underline"
              >
                Dismiss
              </button>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
