"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { SequencePlayer, type TimelineItem } from "./SequencePlayer";
import { ShotLibrary } from "./ShotLibrary";
import { EditorTimeline } from "./EditorTimeline";
import { useLatestJob } from "@/hooks/useGeneration";
import { useLatestJobClips } from "@/hooks/useClips";
import { useStoryboard } from "@/hooks/useStoryboard";
import { useRenderExport, useExportDownload } from "@/hooks/useExport";
import type { GeneratedClip } from "@/lib/types";

/** Pick the best clip per shot (prefer APPROVED, then highest score, must have a URL). */
function buildClipByShot(clips: GeneratedClip[]): Record<string, GeneratedClip> {
  const best: Record<string, GeneratedClip> = {};
  for (const c of clips) {
    if (!c.url) continue;
    const cur = best[c.shot_id];
    const rank = (x: GeneratedClip): [number, number] => [
      x.status === "APPROVED" ? 1 : 0,
      x.consistency_score ?? 0,
    ];
    if (!cur || rank(c) > rank(cur)) best[c.shot_id] = c;
  }
  return best;
}

export function ExportEditor({ projectId }: { projectId: string }) {
  const latestJob = useLatestJob(projectId);
  const storyboard = useStoryboard(projectId);
  const clipsQuery = useLatestJobClips(projectId);
  const render = useRenderExport();
  const download = useExportDownload(projectId);

  // useLatestJob is enabled:false — pull it once on mount to get the job id.
  const refetchJob = latestJob.refetch;
  useEffect(() => {
    refetchJob();
  }, [projectId, refetchJob]);

  const jobId = latestJob.data?.id ?? null;
  const scenes = storyboard.data?.scenes ?? [];
  const clips = clipsQuery.data?.clips ?? [];

  const clipByShot = useMemo(() => buildClipByShot(clips), [clips]);
  const shotLabel = useMemo(() => {
    const m: Record<string, string> = {};
    scenes.forEach((s) =>
      s.shots.forEach((sh) => {
        m[sh.id] = `S${s.scene_number}·Shot ${sh.number}`;
      })
    );
    return m;
  }, [scenes]);

  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [selected, setSelected] = useState(0);
  const [rendering, setRendering] = useState(false);
  const initialized = useRef(false);

  // AI default: pre-fill the timeline with every shot's clip, in order.
  useEffect(() => {
    if (initialized.current) return;
    if (scenes.length === 0 || clips.length === 0) return;
    const items: TimelineItem[] = [];
    for (const scene of scenes) {
      for (const shot of scene.shots) {
        const clip = clipByShot[shot.id];
        if (clip?.url) {
          items.push({
            clipId: clip.id,
            shotId: shot.id,
            url: clip.url,
            label: shotLabel[shot.id] || `Shot ${shot.number}`,
            score: clip.consistency_score,
          });
        }
      }
    }
    if (items.length) {
      setTimeline(items);
      initialized.current = true;
    }
  }, [scenes, clips, clipByShot, shotLabel]);

  const inTimeline = useMemo(
    () => new Set(timeline.map((t) => t.clipId)),
    [timeline]
  );

  const addShot = (shotId: string) => {
    const clip = clipByShot[shotId];
    if (!clip?.url) return;
    setTimeline((t) =>
      t.some((i) => i.clipId === clip.id)
        ? t
        : [
            ...t,
            {
              clipId: clip.id,
              shotId,
              url: clip.url!,
              label: shotLabel[shotId] || "Shot",
              score: clip.consistency_score,
            },
          ]
    );
  };

  const removeClip = (clipId: string) => {
    setTimeline((t) => t.filter((i) => i.clipId !== clipId));
    setSelected((s) => Math.max(0, s - 1));
  };

  const handleExport = async () => {
    if (!jobId || timeline.length === 0) return;
    setRendering(true);
    try {
      await render.mutateAsync({
        projectId,
        jobId,
        clipIds: timeline.map((t) => t.clipId),
      });
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 3000));
        const res = await download.refetch();
        if (res.data?.download_url || res.data?.url) break;
      }
    } finally {
      setRendering(false);
    }
  };

  const result = download.data;

  if (!latestJob.isLoading && !jobId) {
    return (
      <div className="rounded-xl border hairline bg-card p-8 text-center text-sm text-muted-foreground">
        No generated clips yet. Run <span className="text-foreground">Generate</span>{" "}
        first, then come back to assemble your cut.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* top: preview (left) + shot library (right) */}
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <SequencePlayer
            items={timeline}
            index={selected}
            onIndexChange={setSelected}
          />
        </div>
        <ShotLibrary
          scenes={scenes}
          clipByShot={clipByShot}
          inTimeline={inTimeline}
          onAdd={addShot}
        />
      </div>

      {/* bottom: timeline */}
      <EditorTimeline
        items={timeline}
        selectedIndex={selected}
        onSelect={setSelected}
        onReorder={setTimeline}
        onRemove={removeClip}
      />

      {/* export bar */}
      <div className="rounded-xl border hairline glass p-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="font-semibold">Export your cut</h2>
          <p className="text-sm text-muted-foreground">
            Renders the {timeline.length} clips above, in this order, into one MP4.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {result?.download_url || result?.url ? (
            <a
              href={result.download_url || result.url || "#"}
              target="_blank"
              rel="noreferrer"
            >
              <Button variant="outline">⬇ Download MP4</Button>
            </a>
          ) : null}
          {result?.caption_url ? (
            <a href={result.caption_url} target="_blank" rel="noreferrer">
              <Button variant="ghost" size="sm">
                .srt
              </Button>
            </a>
          ) : null}
          <Button
            onClick={handleExport}
            disabled={rendering || timeline.length === 0}
            className="glow"
            size="lg"
          >
            {rendering ? "Rendering…" : "🎬 Export final MP4"}
          </Button>
        </div>
      </div>

      {result?.report_json ? (
        <div className="rounded-xl border hairline bg-card p-4 text-sm">
          <div className="flex items-center justify-between mb-2">
            <p className="font-medium">Production report</p>
            <span
              className={`text-xs ${
                result.report_json.within_budget ? "text-ok" : "text-bad"
              }`}
            >
              {result.report_json.within_budget
                ? "✓ within budget"
                : "over budget"}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <Stat
              label="Duration"
              value={`${result.report_json.total_duration_seconds ?? "—"}s`}
            />
            <Stat label="Clips" value={String(result.report_json.total_clips)} />
            <Stat
              label="Video cost"
              value={`$${result.report_json.video_cost_usd?.toFixed(2)}`}
            />
            <Stat
              label="Grand total"
              value={`$${result.report_json.grand_total_cost?.toFixed(2)} / $${result.report_json.budget_usd}`}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-background/40 p-2.5">
      <p className="text-muted-foreground">{label}</p>
      <p className="text-foreground font-medium mt-0.5">{value}</p>
    </div>
  );
}
