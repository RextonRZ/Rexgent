"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
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
  finalize: "Finalizing plan",
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
  const router = useRouter();
  const [premise, setPremise] = useState(initialPremise);
  const [genre, setGenre] = useState(initialGenre || "sci-fi");
  const [language, setLanguage] = useState("en");
  const [targetLength, setTargetLength] = useState(30); // seconds
  const [episodeCount, setEpisodeCount] = useState(1);
  const [trace, setTrace] = useState<string[]>([]);
  const [result, setResult] = useState<AutoRunResult | null>(null);
  const [touched, setTouched] = useState(false);
  const autoRun = useAutoRun();

  // Rough pre-flight scope estimate (the agent computes the real budget).
  // ~1 short scene per 15s, ~3 shots per scene.
  const estScenes = episodeCount * Math.max(1, Math.round(targetLength / 15));
  const estShots = estScenes * 3;

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
      target_length: targetLength,
      episode_count: episodeCount,
      dispatch_video: false, // plan only — the user spends on the Generate tab
    });
    setResult(res);
  };

  return (
    <Card className="py-6">
      <CardHeader className="px-6">
        <CardTitle>Full Auto — One Premise → Whole Drama</CardTitle>
      </CardHeader>
      <CardContent className="px-6 space-y-5">
        <p className="text-sm text-muted-foreground">
          The agent autonomously writes the script, judges it (and self-corrects
          if weak), extracts characters, storyboards, and allocates the budget —
          then hands you a plan to review. No voucher is spent until you start
          generation on the Generate tab.
        </p>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label>Genre</Label>
            <Input
              value={genre}
              onChange={(e) => {
                setTouched(true);
                setGenre(e.target.value);
              }}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Language</Label>
            <Select value={language} onValueChange={(v) => v && setLanguage(v)}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="en">English</SelectItem>
                <SelectItem value="zh">中文</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="space-y-1.5">
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

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label>Episodes</Label>
            <Input
              type="number"
              min={1}
              max={20}
              value={episodeCount}
              onChange={(e) =>
                setEpisodeCount(Math.max(1, Number(e.target.value) || 1))
              }
            />
          </div>
          <div className="space-y-1.5">
            <Label>Target length (sec/ep)</Label>
            <Input
              type="number"
              min={10}
              max={600}
              step={5}
              value={targetLength}
              onChange={(e) =>
                setTargetLength(Math.max(10, Number(e.target.value) || 10))
              }
            />
          </div>
        </div>

        <div className="rounded-lg border hairline bg-muted/30 p-3 text-xs text-muted-foreground space-y-1">
          <p>
            <span className="text-foreground font-medium">Scope:</span> ≈{" "}
            {estScenes} scenes · ~{estShots} shots at this length.
          </p>
          <p>
            Scripting is cheap — your <span className="text-foreground">$40</span>{" "}
            voucher caps how much <em>video</em> renders, not how long you write.
            A bigger story renders as more, shorter shots; the agent tiers
            premium generation to fit and tells you the real budget before you
            spend.
          </p>
        </div>

        <Button
          onClick={handleRun}
          disabled={!premise || autoRun.isPending}
          className="w-full"
        >
          {autoRun.isPending ? "Planning…" : "Plan my drama (no spend)"}
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
          <div className="border-t pt-3 text-sm space-y-2">
            <p className="font-medium">✓ Plan ready</p>
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
                Projected video budget:{" "}
                <span className="text-foreground font-medium">
                  $
                  {(result.budget.grand_total_cost ??
                    result.budget.total_estimated_cost ??
                    0).toFixed(2)}
                </span>{" "}
                / $40 · {result.budget.wan_shots} Wan /{" "}
                {result.budget.happyhorse_shots} HappyHorse
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              Nothing spent yet. Review the script, cast and storyboard — then
              generate when you&apos;re ready.
            </p>
            <Button
              onClick={() => router.push(`/projects/${projectId}/generate`)}
              className="w-full glow"
            >
              Review &amp; generate →
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
