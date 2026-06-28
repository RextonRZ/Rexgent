"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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
  PROCEED: "bg-green-500",
  REVISE_FIRST: "bg-yellow-500",
  MAJOR_REWRITE: "bg-red-500",
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
            <span className="text-2xl font-bold">
              {result.overall.toFixed(1)}
            </span>
            <Badge className={REC_COLORS[result.recommendation]}>
              {result.recommendation.replace("_", " ")}
            </Badge>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {radarData.length > 0 && (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData}>
                <PolarGrid />
                <PolarAngleAxis dataKey="axis" tick={{ fontSize: 12 }} />
                <PolarRadiusAxis
                  angle={30}
                  domain={[0, 10]}
                  tick={{ fontSize: 10 }}
                />
                <Radar
                  name="Score"
                  dataKey="score"
                  stroke="#2563eb"
                  fill="#2563eb"
                  fillOpacity={0.2}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        )}

        {result.blocking_issues.length > 0 && (
          <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-3">
            <p className="text-sm font-medium text-destructive mb-1">
              Blocking Issues:
            </p>
            <ul className="text-sm space-y-1">
              {result.blocking_issues.map((issue, i) => (
                <li key={i}>{issue}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm font-medium text-green-600 mb-1">Strengths</p>
            <ul className="text-sm space-y-1">
              {result.top_strengths.map((s, i) => (
                <li key={i}>+ {s}</li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-sm font-medium text-orange-600 mb-1">
              Weaknesses
            </p>
            <ul className="text-sm space-y-1">
              {result.top_weaknesses.map((w, i) => (
                <li key={i}>- {w}</li>
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
