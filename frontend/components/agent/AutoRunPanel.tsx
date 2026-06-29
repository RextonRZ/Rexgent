"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAutoRun, type AutoRunResult } from "@/hooks/useAgent";
import { getSocket } from "@/lib/websocket";

const NODE_LABELS: Record<string, string> = {
  generate_script: "Writing script",
  judge: "Judging quality",
  revise: "Revising (self-correction)",
  extract_characters: "Extracting characters",
  storyboard: "Storyboarding",
  budget: "Allocating budget",
  generate_video: "Dispatching video generation",
};

export function AutoRunPanel({
  projectId,
  initialPremise = "",
  initialGenre = "sci-fi",
}: {
  projectId: string;
  initialPremise?: string;
  initialGenre?: string;
}) {
  const [premise, setPremise] = useState(initialPremise);
  const [genre, setGenre] = useState(initialGenre || "sci-fi");
  const [language, setLanguage] = useState("en");
  const [trace, setTrace] = useState<string[]>([]);
  const [result, setResult] = useState<AutoRunResult | null>(null);
  const [touched, setTouched] = useState(false);
  const autoRun = useAutoRun();

  // The project premise arrives asynchronously; seed it once if the user
  // hasn't started editing.
  useEffect(() => {
    if (initialPremise && !touched) setPremise(initialPremise);
  }, [initialPremise, touched]);

  useEffect(() => {
    if (initialGenre && !touched) setGenre(initialGenre);
  }, [initialGenre, touched]);

  useEffect(() => {
    const socket = getSocket();
    socket.connect();
    socket.emit("join_project", { project_id: projectId });
    socket.on("agent:node", (d: { node: string }) => {
      setTrace((t) => [...t, d.node]);
    });
    return () => {
      socket.off("agent:node");
    };
  }, [projectId]);

  const handleRun = async () => {
    setTrace([]);
    setResult(null);
    const res = await autoRun.mutateAsync({
      project_id: projectId,
      premise,
      genre,
      language,
    });
    setResult(res);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Full Auto — One Premise → Whole Drama</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          The agent autonomously writes the script, judges it (and self-corrects
          if weak), extracts characters, storyboards, allocates the budget, and
          kicks off video generation — no clicking through each step.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label>Genre</Label>
            <Input
              value={genre}
              onChange={(e) => {
                setTouched(true);
                setGenre(e.target.value);
              }}
            />
          </div>
          <div>
            <Label>Language</Label>
            <Select value={language} onValueChange={(v) => v && setLanguage(v)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="en">English</SelectItem>
                <SelectItem value="zh">中文</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <div>
          <Label>Premise</Label>
          <Textarea
            value={premise}
            onChange={(e) => {
              setTouched(true);
              setPremise(e.target.value.slice(0, 300));
            }}
            placeholder="A detective in 2047 Tokyo discovers her partner is an AI."
            rows={2}
          />
        </div>
        <Button
          onClick={handleRun}
          disabled={!premise || autoRun.isPending}
          className="w-full"
        >
          {autoRun.isPending ? "Agent running..." : "Run Full Auto"}
        </Button>

        {trace.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs font-medium">Agent trace</p>
            <div className="flex flex-wrap gap-1">
              {trace.map((node, i) => (
                <Badge key={i} variant="secondary" className="text-xs">
                  {NODE_LABELS[node] || node}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {result && (
          <div className="border-t pt-3 text-sm space-y-1">
            <p className="font-medium">Pipeline complete</p>
            {result.judgement && (
              <p>
                Quality:{" "}
                <Badge>{result.judgement.recommendation}</Badge>{" "}
                {result.judgement.overall?.toFixed?.(1)}/10
              </p>
            )}
            <p>
              {result.characters} characters · {result.shots} shots ·{" "}
              {result.revisions} self-revision(s)
            </p>
            {result.budget && (
              <p>
                Budget: $
                {(result.budget.grand_total_cost ??
                  result.budget.total_estimated_cost ??
                  0).toFixed(2)}{" "}
                / $40 · {result.budget.wan_shots} Wan /{" "}
                {result.budget.happyhorse_shots} HappyHorse
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              Video generation dispatched — watch the Generate tab for live
              progress.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
