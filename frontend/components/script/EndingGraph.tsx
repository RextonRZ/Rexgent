"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface EndingAlternative {
  id: string;
  title: string;
  summary: string;
  emotional_tone: string;
  compatibility_score: number;
}

interface EndingGraphProps {
  hasCompleteEnding: boolean;
  endingQuality: string;
  analysis: {
    main_conflict_resolved: boolean;
    protagonist_arc_complete: boolean;
    emotional_payoff: string;
    open_threads: string[];
  };
  alternatives: EndingAlternative[];
  onSelectEnding?: (endingId: string) => void;
}

const TONE_COLORS: Record<string, string> = {
  BITTERSWEET: "bg-amber-100 text-amber-800 border-amber-300",
  HOPEFUL: "bg-teal-100 text-teal-800 border-teal-300",
  AMBIGUOUS: "bg-purple-100 text-purple-800 border-purple-300",
  TRAGIC: "bg-red-100 text-red-800 border-red-300",
  TRIUMPHANT: "bg-green-100 text-green-800 border-green-300",
};

export function EndingGraph({
  hasCompleteEnding,
  endingQuality,
  analysis,
  alternatives,
  onSelectEnding,
}: EndingGraphProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Ending Analysis</span>
          <Badge variant={hasCompleteEnding ? "default" : "destructive"}>
            {endingQuality}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div className="flex items-center gap-2">
            <span
              className={
                analysis.main_conflict_resolved
                  ? "text-green-600"
                  : "text-red-600"
              }
            >
              {analysis.main_conflict_resolved ? "✓" : "✗"}
            </span>
            Main conflict resolved
          </div>
          <div className="flex items-center gap-2">
            <span
              className={
                analysis.protagonist_arc_complete
                  ? "text-green-600"
                  : "text-red-600"
              }
            >
              {analysis.protagonist_arc_complete ? "✓" : "✗"}
            </span>
            Protagonist arc complete
          </div>
        </div>

        {analysis.open_threads.length > 0 && (
          <div>
            <p className="text-sm font-medium mb-1">Open Threads:</p>
            <ul className="text-sm text-muted-foreground space-y-1">
              {analysis.open_threads.map((thread, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="text-yellow-500 mt-0.5">{"⚠"}</span>
                  {thread}
                </li>
              ))}
            </ul>
          </div>
        )}

        {alternatives.length > 0 && (
          <div className="space-y-3">
            <p className="text-sm font-medium">Alternative Endings:</p>
            {alternatives.map((alt) => (
              <div
                key={alt.id}
                className={`border rounded-lg p-3 space-y-2 ${
                  TONE_COLORS[alt.emotional_tone] || ""
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-sm">{alt.title}</span>
                  <Badge variant="outline">
                    {alt.compatibility_score.toFixed(1)}/10
                  </Badge>
                </div>
                <p className="text-sm">{alt.summary}</p>
                {onSelectEnding && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onSelectEnding(alt.id)}
                  >
                    Use This Ending
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
