"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from "recharts";

export interface JudgeResult {
  scores: Record<string, number>;
  overall: number;
  blocking_issues: string[];
  top_strengths: string[];
  top_weaknesses: string[];
  recommendation: "PROCEED" | "REVISE_FIRST" | "MAJOR_REWRITE";
  judge_summary: string;
}

const AXIS_LABELS: Record<string, string> = {
  tension_arc: "Tension Arc",
  character_consistency: "Character Consistency",
  pacing: "Pacing",
  dialogue_naturalness: "Dialogue",
  genre_adherence: "Genre Adherence",
};

const REC_COLORS: Record<string, string> = {
  PROCEED: "bg-ok/15 text-ok",
  REVISE_FIRST: "bg-warn/15 text-warn",
  MAJOR_REWRITE: "bg-bad/15 text-bad",
};

export function NarrativeJudgeReport({ result }: { result: JudgeResult }) {
  const radarData = Object.entries(result.scores).map(([key, value]) => ({
    axis: AXIS_LABELS[key] || key,
    score: value,
    fullMark: 10,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Script Quality Score</span>
          <div className="flex items-center gap-2">
            <span className="text-2xl font-bold tabular-nums">
              {result.overall.toFixed(1)}
            </span>
            <span
              className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                REC_COLORS[result.recommendation] ||
                "bg-secondary text-muted-foreground"
              }`}
            >
              {result.recommendation.replace("_", " ")}
            </span>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {radarData.length > 0 && (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData}>
                <PolarGrid stroke="rgba(148,163,184,0.2)" />
                <PolarAngleAxis
                  dataKey="axis"
                  tick={{ fontSize: 11, fill: "#9aa3b2" }}
                />
                <PolarRadiusAxis
                  angle={30}
                  domain={[0, 10]}
                  tick={{ fontSize: 10, fill: "#9aa3b2" }}
                  stroke="rgba(148,163,184,0.2)"
                />
                <Radar
                  name="Score"
                  dataKey="score"
                  stroke="#8b5cf6"
                  fill="#8b5cf6"
                  fillOpacity={0.25}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        )}

        {result.blocking_issues.length > 0 && (
          <div className="bg-bad/10 border border-bad/20 rounded-lg p-3">
            <p className="text-sm font-medium text-bad mb-1">Blocking issues</p>
            <ul className="text-sm space-y-1 text-muted-foreground">
              {result.blocking_issues.map((issue, i) => (
                <li key={i}>{issue}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4 text-xs">
          <div>
            <p className="font-medium text-ok mb-1.5 uppercase tracking-wide text-[10px]">
              Strengths
            </p>
            <ul className="space-y-1 text-muted-foreground">
              {result.top_strengths.map((s, i) => (
                <li key={i} className="flex gap-1.5">
                  <span className="text-ok shrink-0">+</span> {s}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="font-medium text-warn mb-1.5 uppercase tracking-wide text-[10px]">
              Weaknesses
            </p>
            <ul className="space-y-1 text-muted-foreground">
              {result.top_weaknesses.map((w, i) => (
                <li key={i} className="flex gap-1.5">
                  <span className="text-warn shrink-0">−</span> {w}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {result.judge_summary && (
          <p className="text-sm text-muted-foreground italic">
            {result.judge_summary}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
