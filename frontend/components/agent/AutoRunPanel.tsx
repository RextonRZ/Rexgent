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
import { useProject } from "@/hooks/useProjects";
import { getSocket } from "@/lib/websocket";
import { GENRES } from "@/lib/genres";
import { errText } from "@/lib/errText";
import { cn } from "@/lib/utils";

// Preset tones: a deliberate choice, not a blank text box.
const TONES = [
  "dramatic",
  "dark",
  "tense",
  "romantic",
  "lighthearted",
  "comedic",
];

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
  initialEpisodes,
  initialTargetLength,
}: {
  projectId: string;
  initialPremise?: string;
  initialGenre?: string;
  initialEpisodes?: number;
  initialTargetLength?: number;
}) {
  const router = useRouter();
  const { data: project } = useProject(projectId);
  const [premise, setPremise] = useState(initialPremise);
  const [genre, setGenre] = useState(initialGenre || "sci-fi");
  const [tone, setTone] = useState("dramatic");
  // tone reaches the LLM as free prompt text — presets guide, custom frees
  const [customTone, setCustomTone] = useState(false);
  const [model, setModel] = useState("qwen-max");
  const [language, setLanguage] = useState("en");
  const [targetLength, setTargetLength] = useState(initialTargetLength || 30); // seconds
  const [episodeCount, setEpisodeCount] = useState(initialEpisodes || 1);
  const [fullAuto, setFullAuto] = useState(false);
  const [trace, setTrace] = useState<string[]>([]);
  const [result, setResult] = useState<AutoRunResult | null>(null);
  const [touched, setTouched] = useState(false);
  const autoRun = useAutoRun();
  const cap = project?.credit_budget ?? 40;

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

  // Scope stored on the drama at creation arrives async too.
  useEffect(() => {
    if (initialEpisodes && !touched) setEpisodeCount(initialEpisodes);
  }, [initialEpisodes, touched]);
  useEffect(() => {
    if (initialTargetLength && !touched) setTargetLength(initialTargetLength);
  }, [initialTargetLength, touched]);

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

  const [runError, setRunError] = useState<string | null>(null);

  const handleRun = async () => {
    setTrace([]);
    setResult(null);
    setRunError(null);
    try {
      const res = await autoRun.mutateAsync({
        project_id: projectId,
        premise,
        genre,
        tone: tone.trim() || "dramatic",
        model,
        language,
        target_length: targetLength,
        episode_count: episodeCount,
        // Full Auto renders + exports the finished episode under the spend cap;
        // otherwise plan only — the user spends on the Generate tab.
        dispatch_video: fullAuto,
      });
      setResult(res);
    } catch (err) {
      // long runs can outlive the HTTP timeout while STILL progressing
      // server-side — keep the trace visible and say so, never go mute
      setRunError(errText(err));
    }
  };

  return (
    <Card className="py-6">
      <CardHeader className="px-6">
        <CardTitle>Full Auto — One Premise → Whole Drama</CardTitle>
      </CardHeader>
      <CardContent className="px-6 space-y-5">
        <p className="text-sm text-muted-foreground">
          The agent writes your script and judges it, rewriting weak drafts.
          With Full Auto on it then casts, storyboards, renders and exports
          the whole episode by itself. With it off, the run stops at the
          script checkpoint and you continue each stage from the Showrunner
          chat, so nothing runs before you say so. Writing costs a few cents;
          your voucher only goes to plates, voices and video.
        </p>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label>Genre</Label>
            <Select
              value={genre}
              onValueChange={(v) => {
                if (v) {
                  setTouched(true);
                  setGenre(v);
                }
              }}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {GENRES.map((g) => (
                  <SelectItem key={g.value} value={g.value}>
                    <g.icon className="size-3.5 text-muted-foreground" />
                    {g.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Tone</Label>
            <Select
              value={customTone ? "custom" : tone}
              onValueChange={(v) => {
                if (!v) return;
                if (v === "custom") {
                  setCustomTone(true);
                } else {
                  setCustomTone(false);
                  setTone(v);
                }
              }}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TONES.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                  </SelectItem>
                ))}
                <SelectItem value="custom">Custom…</SelectItem>
              </SelectContent>
            </Select>
            {customTone && (
              <Input
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                placeholder="bittersweet neo noir, slow burn, wuxia..."
                autoFocus
              />
            )}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
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
          <div className="space-y-1.5">
            <Label>Writing model</Label>
            <Select value={model} onValueChange={(v) => v && setModel(v)}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="qwen-max">Qwen-Max (best)</SelectItem>
                <SelectItem value="qwen-plus">Qwen-Plus (balanced)</SelectItem>
                <SelectItem value="qwen-flash">Qwen-Flash (fast/cheap)</SelectItem>
                <SelectItem value="qwen3-max">Qwen3-Max (newest)</SelectItem>
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
              onChange={(e) => {
                setTouched(true);
                setEpisodeCount(Math.max(1, Number(e.target.value) || 1));
              }}
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
              onChange={(e) => {
                setTouched(true);
                setTargetLength(Math.max(10, Number(e.target.value) || 10));
              }}
            />
          </div>
        </div>

        <div className="rounded-lg border hairline bg-muted/30 p-3 text-xs text-muted-foreground space-y-1">
          <p>
            <span className="text-foreground font-medium">Scope:</span> ≈{" "}
            {estScenes} scenes · ~{estShots} shots at this length.
          </p>
          <p>
            Scripting costs cents. This drama&apos;s{" "}
            <span className="text-foreground">${cap.toFixed(0)}</span> cap limits
            how much <em>video</em> renders, not how long you write. A bigger
            story renders as more, shorter shots; the agent tiers premium
            generation to fit and tells you the real budget before you spend.
          </p>
        </div>

        <button
          onClick={() => setFullAuto((v) => !v)}
          className={cn(
            "w-full rounded-lg border p-3 text-left transition-all",
            fullAuto
              ? "border-primary bg-primary/10"
              : "border-border hover:border-primary/40"
          )}
        >
          <span className="flex items-center justify-between text-sm font-semibold">
            <span>⚡ Full Auto: premise → finished episode</span>
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[10px] font-medium",
                fullAuto ? "bg-primary/20 text-primary" : "bg-secondary text-muted-foreground"
              )}
            >
              {fullAuto ? "ON" : "OFF"}
            </span>
          </span>
          <span className="mt-0.5 block text-[11px] text-muted-foreground">
            {fullAuto
              ? `Casts, voices, renders and exports the episode automatically under the $${cap.toFixed(0)} cap. This spends your voucher.`
              : "Off: writes and judges the script, then stops. You review it and continue each stage from the Showrunner chat."}
          </span>
        </button>

        <Button
          onClick={handleRun}
          disabled={!premise || autoRun.isPending}
          className="w-full"
        >
          {autoRun.isPending
            ? fullAuto
              ? "Producing your episode…"
              : "Writing…"
            : fullAuto
            ? "Produce my episode (spends voucher)"
            : "Write my script (no video spend)"}
        </Button>

        {runError && (
          <p className="rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
            {runError}
            {trace.length > 0 &&
              " The agent trace below shows how far the run got."}
          </p>
        )}

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
            <p className="font-medium">
              {fullAuto ? "✓ Episode in production" : "✓ Script ready"}
            </p>
            {result.judgement && (
              <p>
                Quality:{" "}
                <Badge>{result.judgement.recommendation}</Badge>{" "}
                {result.judgement.overall?.toFixed?.(1)}/10
              </p>
            )}
            {result.status === "script_ready" ? (
              <p>
                {result.revisions} self-revision(s) before the judge approved
              </p>
            ) : (
              <p>
                {result.characters} characters · {result.shots} shots ·{" "}
                {result.revisions} self-revision(s)
              </p>
            )}
            {result.budget && (
              <p>
                Projected video budget:{" "}
                <span className="text-foreground font-medium">
                  $
                  {(result.budget.grand_total_cost ??
                    result.budget.total_estimated_cost ??
                    0).toFixed(2)}
                </span>{" "}
                / ${cap.toFixed(0)} · {result.budget.wan_shots} Wan /{" "}
                {result.budget.happyhorse_shots} HappyHorse
              </p>
            )}
            {fullAuto ? (
              <p className="text-xs text-muted-foreground">
                Plates, voices and video are rendering automatically. Watch
                progress on the Generate step.
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">
                The run paused at the script checkpoint, nothing else has
                started. Read the script in the editor, then continue from
                the Showrunner chat: cast, storyboard, generate. Only plates,
                voices and video spend your voucher.
              </p>
            )}
            <Button
              onClick={() =>
                router.push(
                  `/projects/${projectId}/${fullAuto ? "generate" : "script"}`
                )
              }
              className="w-full glow"
            >
              {fullAuto ? "Watch it render →" : "Review the script →"}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
