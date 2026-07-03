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

// tone chip colors on the dark theme (semantic tokens, no light-mode pastels)
const TONE_COLORS: Record<string, string> = {
  BITTERSWEET: "bg-warn/15 text-warn",
  HOPEFUL: "bg-ok/15 text-ok",
  AMBIGUOUS: "bg-primary/15 text-primary",
  TRAGIC: "bg-bad/15 text-bad",
  TRIUMPHANT: "bg-ok/15 text-ok",
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
                analysis.main_conflict_resolved ? "text-ok" : "text-bad"
              }
            >
              {analysis.main_conflict_resolved ? "✓" : "✗"}
            </span>
            Main conflict resolved
          </div>
          <div className="flex items-center gap-2">
            <span
              className={
                analysis.protagonist_arc_complete ? "text-ok" : "text-bad"
              }
            >
              {analysis.protagonist_arc_complete ? "✓" : "✗"}
            </span>
            Protagonist arc complete
          </div>
        </div>

        {analysis.open_threads.length > 0 && (
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-1.5">
              Open threads
            </p>
            <ul className="text-sm text-muted-foreground space-y-1">
              {analysis.open_threads.map((thread, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-warn shrink-0" />
                  {thread}
                </li>
              ))}
            </ul>
          </div>
        )}

        {alternatives.length > 0 && (
          <div className="space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Alternative endings
            </p>
            {alternatives.map((alt) => (
              <div
                key={alt.id}
                className="border border-border rounded-lg p-3 space-y-2 bg-background/40"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-sm">{alt.title}</span>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                        TONE_COLORS[alt.emotional_tone] ||
                        "bg-secondary text-muted-foreground"
                      }`}
                    >
                      {alt.emotional_tone.toLowerCase()}
                    </span>
                    <Badge variant="outline">
                      {alt.compatibility_score.toFixed(1)}/10
                    </Badge>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground">{alt.summary}</p>
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
