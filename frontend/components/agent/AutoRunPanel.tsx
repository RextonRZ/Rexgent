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
import { useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { useAutoRun, type AutoRunResult } from "@/hooks/useAgent";
import { useProject } from "@/hooks/useProjects";
import { useBible } from "@/hooks/useCasting";
import { GENRES } from "@/lib/genres";
import { PHOTOREAL, VISUAL_STYLES } from "@/lib/styles";
import { SampleCard } from "@/components/shared/SampleCard";
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

// what each preset actually does to the writing, so the pick is informed
const TONE_NOTES: Record<string, string> = {
  dramatic: "Big emotions played straight. Confrontations, confessions, high stakes.",
  dark: "Heavy and unsettling. Grim choices and moral weight over everything.",
  tense: "Pressure that keeps building. Secrets, deadlines, danger close by.",
  romantic: "Longing and chemistry lead. Tender beats between the drama.",
  lighthearted: "Warm and easygoing. Gentle humor and feel good endings.",
  comedic: "Played for laughs. Timing, banter and awkward situations first.",
};

export function AutoRunPanel({
  projectId,
  initialPremise = "",
  initialGenre = "sci-fi",
  initialEpisodes,
  initialTargetLength,
  onScriptReady,
  mode = "create",
  onRewritten,
}: {
  projectId: string;
  initialPremise?: string;
  initialGenre?: string;
  initialEpisodes?: number;
  initialTargetLength?: number;
  /** fires when a checkpoint run finishes writing the script, with the run
   * result — the Script page uses it to surface the judge's report */
  onScriptReady?: (result: AutoRunResult) => void;
  mode?: "create" | "rewrite";
  /** rewrite mode: fired after a new draft is written, so the caller can close the dialog */
  onRewritten?: () => void;
}) {
  const router = useRouter();
  const rewrite = mode === "rewrite";
  const { data: project } = useProject(projectId);
  const [premise, setPremise] = useState(initialPremise);
  // default to drama, the platform's home genre: a silent "sci-fi" default
  // injected sci-fi beats into premises that never asked for them
  const [genre, setGenre] = useState(initialGenre || "drama");
  const [visualStyle, setVisualStyle] = useState<string>(PHOTOREAL);
  const [ratio, setRatio] = useState<"9:16" | "16:9">("9:16");
  const [tone, setTone] = useState("dramatic");
  // tone reaches the LLM as free prompt text — presets guide, custom frees
  const [customTone, setCustomTone] = useState(false);
  const [model, setModel] = useState("qwen-max");
  const [language, setLanguage] = useState("en");
  const [targetLength, setTargetLength] = useState(initialTargetLength || 30); // seconds
  const [episodeCount, setEpisodeCount] = useState(initialEpisodes || 1);
  const [fullAuto, setFullAuto] = useState(false);
  const [result, setResult] = useState<AutoRunResult | null>(null);
  const [touched, setTouched] = useState(false);
  const autoRun = useAutoRun();
  const queryClient = useQueryClient();
  const cap = project?.credit_budget ?? 40;

  const [budget, setBudget] = useState<number>(project?.credit_budget ?? 40);
  useEffect(() => {
    if (project?.credit_budget != null) setBudget(project.credit_budget);
  }, [project?.credit_budget]);

  const { data: bible } = useBible(projectId);
  const hasCast = Boolean(
    bible?.characters?.some(
      (c) => c.voice_id || c.variants?.some((v) => v.plate_image_url)
    )
  );

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

  // the look picked at creation arrives with the project; mirror it until
  // the user changes it here
  useEffect(() => {
    if (project && !touched) setVisualStyle(project.visual_style ?? PHOTOREAL);
  }, [project, touched]);

  useEffect(() => {
    if (project?.video_ratio === "9:16" || project?.video_ratio === "16:9")
      setRatio(project.video_ratio);
  }, [project?.video_ratio]);

  // Scope stored on the drama at creation arrives async too.
  useEffect(() => {
    if (initialEpisodes && !touched) setEpisodeCount(initialEpisodes);
  }, [initialEpisodes, touched]);
  useEffect(() => {
    if (initialTargetLength && !touched) setTargetLength(initialTargetLength);
  }, [initialTargetLength, touched]);

  const [runError, setRunError] = useState<string | null>(null);

  const handleRun = async () => {
    setResult(null);
    setRunError(null);
    try {
      if (rewrite) {
        // persist the tweaked scope + budget before the run, so the drama's
        // stored settings follow the new draft
        await api.patch(`/api/projects/${projectId}`, {
          episode_count: episodeCount,
          target_length: targetLength,
          credit_budget: budget,
        });
      }
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
        // otherwise the run stops at the script checkpoint. Rewrite never
        // dispatches video — it only writes a fresh draft.
        dispatch_video: rewrite ? false : fullAuto,
      });
      setResult(res);
      if (rewrite || !fullAuto) {
        // the script exists NOW — refresh the queries so the Script page
        // flips straight into the editor instead of hanging on stale data,
        // and hand the judge's report up for the analysis rail
        onScriptReady?.(res);
        queryClient.invalidateQueries({ queryKey: ["latest-script", projectId] });
        queryClient.invalidateQueries({ queryKey: ["progress", projectId] });
        queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      }
      if (rewrite) onRewritten?.();
    } catch (err) {
      // long runs can outlive the HTTP timeout while STILL progressing
      // server-side — say so, never go mute
      setRunError(errText(err));
    }
  };

  return (
    // in rewrite mode the panel lives inside a dialog that already shows the
    // title, so the Card chrome and duplicate heading disappear
    <Card className={rewrite ? "border-0 bg-transparent py-0 shadow-none" : "py-6"}>
      {!rewrite && (
        <CardHeader className="px-6">
          <CardTitle>Full Auto — One Premise → Whole Drama</CardTitle>
        </CardHeader>
      )}
      <CardContent className={rewrite ? "px-0 space-y-5" : "px-6 space-y-5"}>
        <p className="text-sm text-muted-foreground">
          {rewrite
            ? "Adjust the premise, scope or budget and write a fresh draft. Your current draft stays in history."
            : `The agent writes your script and judges it, rewriting weak drafts.
          With Full Auto on it then casts, storyboards, renders and exports
          the whole episode by itself. With it off, the run stops at the
          script checkpoint and you continue each stage from the Showrunner
          chat, so nothing runs before you say so. Writing costs a few cents;
          your voucher only goes to plates and video.`}
        </p>
        <div>
          <div className="flex items-baseline justify-between">
            <Label>Genre</Label>
            <span className="text-[11px] font-medium text-primary">
              {GENRES.find((g) => g.value === genre)?.label}
            </span>
          </div>
          <div className="scroll-clean mt-1.5 flex snap-x gap-2 overflow-x-auto pb-1.5">
            {GENRES.map((g) => (
              <SampleCard
                key={g.value}
                active={genre === g.value}
                onClick={() => {
                  setTouched(true);
                  setGenre(g.value);
                  // persist immediately: the drama's stored genre must follow
                  // this choice, or rewrites and later stages keep the old one
                  api
                    .patch(`/api/projects/${projectId}`, { genre: g.value })
                    .then(() =>
                      queryClient.invalidateQueries({
                        queryKey: ["project", projectId],
                      })
                    )
                    .catch(() => {});
                }}
                img={`/genres/${g.value.replace(/ /g, "-")}.jpg`}
                label={g.label}
              />
            ))}
          </div>
        </div>

        <div>
          <div className="flex items-baseline justify-between">
            <Label>Visual style</Label>
            <span className="text-[11px] font-medium text-primary">
              {VISUAL_STYLES.find((s) => s.value === visualStyle)?.label}
            </span>
          </div>
          <div className="scroll-clean mt-1.5 flex snap-x gap-2 overflow-x-auto pb-1.5">
            {VISUAL_STYLES.map((s) => (
              <SampleCard
                key={s.value}
                active={visualStyle === s.value}
                onClick={() => {
                  setTouched(true);
                  setVisualStyle(s.value);
                  // persist immediately so casting paints the plates in this
                  // look; sending photoreal clears the stored style
                  api
                    .patch(`/api/projects/${projectId}`, {
                      visual_style: s.value,
                    })
                    .then(() =>
                      queryClient.invalidateQueries({
                        queryKey: ["project", projectId],
                      })
                    )
                    .catch(() => {});
                }}
                img={`/styles/${s.value}.jpg`}
                label={s.label}
              />
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
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
            <p className="text-[11px] text-muted-foreground">
              {customTone
                ? "Describe the mood in your own words. It reaches the writers directly."
                : TONE_NOTES[tone] ?? "How the story should feel to watch."}
            </p>
          </div>
          <div className="space-y-1.5">
            <Label>Format</Label>
            <div className="grid grid-cols-2 gap-2">
              {(["9:16", "16:9"] as const).map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => {
                    setRatio(r);
                    // persist immediately: generation, export canvas and the
                    // player all read the drama's stored format
                    api
                      .patch(`/api/projects/${projectId}`, { video_ratio: r })
                      .then(() =>
                        queryClient.invalidateQueries({
                          queryKey: ["project", projectId],
                        })
                      )
                      .catch(() => {});
                  }}
                  className={cn(
                    "flex items-center justify-center gap-2 rounded-md border px-2 py-2 text-xs transition-all",
                    ratio === r
                      ? "border-primary bg-primary/10 font-medium"
                      : "border-border text-muted-foreground hover:border-primary/40"
                  )}
                >
                  <span
                    className={cn(
                      "shrink-0 rounded-[2px] border",
                      r === "9:16" ? "h-4 w-2.5" : "h-2.5 w-4",
                      ratio === r
                        ? "border-primary bg-primary/25"
                        : "border-muted-foreground/50"
                    )}
                  />
                  {r === "9:16" ? "Vertical" : "Landscape"}
                </button>
              ))}
            </div>
            <p className="text-[11px] text-muted-foreground">
              {ratio === "9:16"
                ? "Short drama for phones. Recommended."
                : "Widescreen for desktop and TV."}
            </p>
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
              // generous cap: a rich, scenery-forward premise runs a few hundred
              // words; the guard only stops an accidental novel-length paste
              setPremise(e.target.value.slice(0, 2000));
            }}
            placeholder="A detective in 2047 Tokyo discovers her partner is an AI."
            rows={6}
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
            <Label>Length guide (sec/ep)</Label>
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
            <p className="text-[11px] text-muted-foreground">
              A pacing guide, not an exact cut: clips render in fixed lengths,
              so the finished episode usually runs a little over this number.
            </p>
          </div>
        </div>

        {rewrite && (
          <div className="space-y-1.5">
            <Label>Spend cap ($)</Label>
            <Input
              type="number"
              min={5}
              step={5}
              value={budget}
              onChange={(e) =>
                setBudget(Math.max(5, Number(e.target.value) || 5))
              }
            />
          </div>
        )}

        <div className="rounded-lg border hairline bg-muted/30 p-3 text-xs text-muted-foreground space-y-1">
          <p>
            <span className="text-foreground font-medium">Scope:</span> ≈{" "}
            {estScenes} scenes · ~{estShots} shots at this length.
          </p>
          <p>
            Scripting costs cents. This drama&apos;s{" "}
            <span className="text-foreground">${cap.toFixed(0)}</span> cap limits
            how much <em>video</em> renders, not how long you write. A bigger
            story renders as more, shorter shots; the agent eases lower-priority
            shots to a faster pass to fit and tells you the real budget before
            you spend.
          </p>
        </div>

        {!rewrite && (
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
                ? `Casts, renders and exports the episode automatically under the $${cap.toFixed(0)} cap. This spends your voucher.`
                : "Off: writes and judges the script, then stops. You review it and continue each stage from the Showrunner chat."}
            </span>
          </button>
        )}

        {rewrite && hasCast && (
          <p className="rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-[11px] leading-4 text-amber-300">
            You already cast this drama. Rewriting changes the script, so your cast may no longer match. Nothing is deleted, recast whatever changed when you are ready.
          </p>
        )}

        {runError && (
          <p className="rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
            {runError} The Showrunner chat and crew dock show how far the run
            got.
          </p>
        )}

        {/* in the rewrite dialog the button FLOATS at the bottom of the
            scroll viewport: always in reach, flush with the dialog edge,
            the form fading out beneath it in the dialog's glass colour */}
        <div
          className={
            rewrite
              ? "sticky bottom-0 z-10 -mx-4 rounded-b-xl bg-gradient-to-t from-[hsl(250_20%_10%)] via-[hsl(250_20%_10%/0.92)] to-transparent px-4 pt-6 pb-3"
              : undefined
          }
        >
          <Button
            onClick={handleRun}
            disabled={!premise || autoRun.isPending}
            className="w-full"
          >
            {rewrite
              ? autoRun.isPending
                ? "Rewriting…"
                : "Rewrite my script (no video spend)"
              : autoRun.isPending
              ? fullAuto
                ? "Producing your episode…"
                : "Writing…"
              : fullAuto
              ? "Produce my episode (spends voucher)"
              : "Write my script (no video spend)"}
          </Button>
        </div>

        {result && !rewrite && (
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
                / ${cap.toFixed(0)} ·{" "}
                {result.budget.wan_shots || result.budget.happyhorse_shots
                  ? [
                      result.budget.wan_shots
                        ? `${result.budget.wan_shots} Wan`
                        : null,
                      result.budget.happyhorse_shots
                        ? `${result.budget.happyhorse_shots} HappyHorse`
                        : null,
                    ]
                      .filter(Boolean)
                      .join(" / ")
                  : `${result.budget.full_shots} full / ${result.budget.fast_shots} fast`}
              </p>
            )}
            {fullAuto ? (
              <p className="text-xs text-muted-foreground">
                Plates and video are rendering automatically. Watch
                progress on the Generate step.
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">
                The run paused at the script checkpoint, nothing else has
                started. Read the script in the editor, then continue from
                the Showrunner chat: cast, storyboard, generate. Only plates
                and video spend your voucher.
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
