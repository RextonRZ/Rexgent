"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  SequencePlayer,
  type PreviewSegment,
  type TimelineItem,
} from "./SequencePlayer";
import { ShotLibrary } from "./ShotLibrary";
import {
  EditorTimeline,
  EMPTY_AUDIO,
  type AudioSettings,
} from "./EditorTimeline";
import { MediaBin, type MediaAsset } from "./MediaBin";
import { ClipEditModal } from "./ClipEditModal";
import { useLatestJob } from "@/hooks/useGeneration";
import { useLatestJobClips } from "@/hooks/useClips";
import { useProject } from "@/hooks/useProjects";
import { useStoryboard } from "@/hooks/useStoryboard";
import {
  useRenderExport,
  useExportDownload,
  useUploadAudio,
  useUploadMedia,
} from "@/hooks/useExport";
import api from "@/lib/api";
import { LiveStageStrip } from "@/components/shared/LiveStageStrip";
import type { GeneratedClip } from "@/lib/types";
import { errText } from "@/lib/errText";

/** All playable takes per shot, best first (APPROVED, then highest score). */
function buildClipsByShot(clips: GeneratedClip[]): Record<string, GeneratedClip[]> {
  const byShot: Record<string, GeneratedClip[]> = {};
  for (const c of clips) {
    if (!c.url) continue;
    (byShot[c.shot_id] ??= []).push(c);
  }
  for (const k in byShot) {
    byShot[k].sort((a, b) => {
      const ra = a.status === "APPROVED" ? 1 : 0;
      const rb = b.status === "APPROVED" ? 1 : 0;
      if (ra !== rb) return rb - ra;
      return (b.consistency_score ?? 0) - (a.consistency_score ?? 0);
    });
  }
  return byShot;
}

export function ExportEditor({ projectId }: { projectId: string }) {
  const latestJob = useLatestJob(projectId);
  const { data: project } = useProject(projectId);
  const storyboard = useStoryboard(projectId);
  const clipsQuery = useLatestJobClips(projectId);
  const render = useRenderExport();
  const download = useExportDownload(projectId);
  const uploadAudio = useUploadAudio(projectId);
  const uploadMedia = useUploadMedia(projectId);

  // useLatestJob is enabled:false — pull it once on mount to get the job id.
  const refetchJob = latestJob.refetch;
  useEffect(() => {
    refetchJob();
  }, [projectId, refetchJob]);

  const jobId = latestJob.data?.id ?? null;
  // stable identities so downstream memos don't recompute every render
  const scenes = useMemo(() => storyboard.data?.scenes ?? [], [storyboard.data]);
  const clips = useMemo(() => clipsQuery.data?.clips ?? [], [clipsQuery.data]);

  // a multi-episode drama edits and exports ONE episode at a time
  const episodesPresent = useMemo(
    () =>
      Array.from(new Set(scenes.map((s) => s.episode ?? 1))).sort(
        (a, b) => a - b
      ),
    [scenes]
  );
  const [activeEp, setActiveEp] = useState<number | null>(null);
  const currentEp = activeEp ?? episodesPresent[0] ?? 1;
  const multiEpisode = episodesPresent.length > 1;
  const epScenes = useMemo(
    () =>
      multiEpisode
        ? scenes.filter((s) => (s.episode ?? 1) === currentEp)
        : scenes,
    [scenes, multiEpisode, currentEp]
  );

  const clipsByShot = useMemo(() => buildClipsByShot(clips), [clips]);
  // takes whose shot no longer exists (storyboard regenerated) — still usable
  const orphanClips = useMemo(() => {
    const shotIds = new Set(scenes.flatMap((s) => s.shots.map((sh) => sh.id)));
    return clips.filter((c) => c.url && !shotIds.has(c.shot_id));
  }, [clips, scenes]);
  const clipByShot = useMemo(() => {
    const m: Record<string, GeneratedClip> = {};
    for (const [shotId, takes] of Object.entries(clipsByShot)) m[shotId] = takes[0];
    return m;
  }, [clipsByShot]);
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
  const [playhead, setPlayhead] = useState(0);
  const [rendering, setRendering] = useState(false);
  const [audio, setAudio] = useState<AudioSettings>(EMPTY_AUDIO);
  const [media, setMedia] = useState<MediaAsset[]>([]);
  const [editingClip, setEditingClip] = useState<GeneratedClip | null>(null);
  const initialized = useRef(false);

  // switching the episode tab starts that episode's cut fresh
  useEffect(() => {
    if (!multiEpisode) return;
    initialized.current = false;
    setTimeline([]);
    setSelected(0);
  }, [currentEp, multiEpisode]);

  // AI default: pre-fill the timeline with every shot's clip, in order.
  useEffect(() => {
    if (initialized.current) return;
    if (epScenes.length === 0 || clips.length === 0) return;
    const items: TimelineItem[] = [];
    for (const scene of epScenes) {
      for (const shot of scene.shots) {
        const clip = clipByShot[shot.id];
        if (clip?.url) {
          items.push({
            clipId: clip.id,
            shotId: shot.id,
            url: clip.url,
            label: shotLabel[shot.id] || `Shot ${shot.number}`,
            score: clip.consistency_score,
            duration: 5,
            trimStart: 0,
            trimEnd: 5,
            trimmed: false,
          });
        }
      }
    }
    if (items.length) {
      setTimeline(items);
      initialized.current = true;
    }
  }, [epScenes, clips, clipByShot, shotLabel]);

  const inTimeline = useMemo(
    () => new Set(timeline.map((t) => t.clipId)),
    [timeline]
  );

  const addClip = (clip: GeneratedClip) => {
    if (!clip.url) return;
    setTimeline((t) =>
      t.some((i) => i.clipId === clip.id)
        ? t
        : [
            ...t,
            {
              clipId: clip.id,
              shotId: clip.shot_id,
              url: clip.url!,
              label: shotLabel[clip.shot_id] || "Earlier take",
              score: clip.consistency_score,
              duration: 5,
              trimStart: 0,
              trimEnd: 5,
              trimmed: false,
            },
          ]
    );
  };

  const removeClip = (clipId: string) => {
    setTimeline((t) => t.filter((i) => i.clipId !== clipId));
    setSelected((s) => Math.max(0, s - 1));
  };

  // Real clip duration from the preview; widen the out-point if untrimmed.
  const handleDuration = (i: number, seconds: number) => {
    if (!seconds || !isFinite(seconds)) return;
    setTimeline((t) =>
      t.map((item, idx) =>
        idx === i
          ? {
              ...item,
              duration: seconds,
              trimEnd: item.trimmed ? Math.min(item.trimEnd, seconds) : seconds,
            }
          : item
      )
    );
  };

  const setTrimById = (clipId: string, start: number, end: number) => {
    setTimeline((t) =>
      t.map((item) =>
        item.clipId === clipId
          ? { ...item, trimStart: start, trimEnd: end, trimmed: true }
          : item
      )
    );
  };

  const prefixSeconds = (i: number) =>
    timeline.slice(0, i).reduce((s, it) => s + (it.trimEnd - it.trimStart), 0);

  const selectClip = (i: number) => {
    setSelected(i);
    setPlayhead(prefixSeconds(i));
  };

  const handleProgress = (i: number, currentTime: number) => {
    const cur = timeline[i];
    if (!cur) return;
    const within = Math.max(
      0,
      Math.min(currentTime - cur.trimStart, cur.trimEnd - cur.trimStart)
    );
    setPlayhead(prefixSeconds(i) + within);
  };

  const handleAudioFile = async (file: File) => {
    const res = await uploadAudio.mutateAsync(file);
    setAudio({ ...audio, url: res.url, name: file.name });
  };

  const handleImportMedia = async (file: File) => {
    const isAudio = file.type.startsWith("audio/");
    const res = isAudio
      ? await uploadAudio.mutateAsync(file)
      : await uploadMedia.mutateAsync(file);
    setMedia((m) => [
      ...m,
      {
        id: crypto.randomUUID(),
        url: res.url,
        name: file.name,
        type: isAudio ? "audio" : "video",
      },
    ]);
  };

  const onAddAsset = (asset: MediaAsset) => {
    if (asset.type === "audio") {
      setAudio({ ...EMPTY_AUDIO, url: asset.url, name: asset.name });
    } else {
      addMedia(asset);
    }
  };

  const addMedia = (asset: MediaAsset) => {
    setTimeline((t) => [
      ...t,
      {
        clipId: asset.id,
        shotId: asset.id,
        url: asset.url,
        label: asset.name.slice(0, 20),
        score: null,
        duration: 5,
        trimStart: 0,
        trimEnd: 5,
        trimmed: false,
        external: true,
      },
    ]);
  };

  const [exportNotice, setExportNotice] = useState<string | null>(null);

  // ── live preview plan: captions + voices placed by the SAME math the
  // export uses, refreshed whenever the timeline changes ──
  const shotMeta = useMemo(() => {
    const m: Record<string, { scene: number; dialogue: string | null }> = {};
    scenes.forEach((s) =>
      s.shots.forEach((sh) => {
        m[sh.id] = { scene: s.scene_number, dialogue: sh.dialogue };
      })
    );
    return m;
  }, [scenes]);
  const [segments, setSegments] = useState<PreviewSegment[]>([]);
  useEffect(() => {
    if (timeline.length === 0) {
      setSegments([]);
      return;
    }
    const entries = timeline.map((t) => {
      const m = shotMeta[t.shotId];
      return {
        scene_number: m?.scene ?? null,
        duration: Math.max(0, t.trimEnd - t.trimStart),
        has_dialogue: Boolean(m?.dialogue),
        text: m?.dialogue ?? null,
      };
    });
    const h = setTimeout(async () => {
      try {
        const { data } = await api.post("/api/export/preview_plan", {
          project_id: projectId,
          entries,
        });
        setSegments(data.segments ?? []);
      } catch {
        // the preview plan is an enhancement, never a blocker
      }
    }, 400);
    return () => clearTimeout(h);
  }, [timeline, shotMeta, projectId]);

  const totalSeconds = useMemo(
    () => timeline.reduce((s, t) => s + Math.max(0, t.trimEnd - t.trimStart), 0),
    [timeline]
  );

  // ── the true rendered file for the open episode, once an export exists ──
  const downloadData = download.data;
  const finalUrl = useMemo(() => {
    const eps = downloadData?.report_json?.episodes;
    if (multiEpisode && eps?.length)
      return eps.find((e) => e.episode === currentEp)?.url ?? null;
    return downloadData?.download_url || downloadData?.url || null;
  }, [downloadData, multiEpisode, currentEp]);
  const [showFinal, setShowFinal] = useState(false);

  // every shot's best take across the WHOLE drama, in story order — the
  // payload for "Export all episodes" regardless of which tab is open
  const buildAllItems = (): TimelineItem[] => {
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
            duration: 5,
            trimStart: 0,
            trimEnd: 5,
            trimmed: false,
          });
        }
      }
    }
    return items;
  };

  const downloadAllZip = async () => {
    const res = await api.get(`/api/export/${projectId}/download_all`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(res.data as Blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "episodes.zip";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExport = async (items?: TimelineItem[]) => {
    const list = items ?? timeline;
    if (!jobId || list.length === 0) return;
    setRendering(true);
    // immediate feedback: a multi-episode render takes minutes, and silence
    // reads as a hang
    setExportNotice(
      `Rendering ${list.length} clips. Live progress shows above; the download buttons appear here when the cut lands.`
    );
    try {
      await render.mutateAsync({
        projectId,
        jobId,
        clips: list.map((t) =>
          t.external
            ? { url: t.url, trim_start: t.trimStart, trim_end: t.trimEnd }
            : { clip_id: t.clipId, trim_start: t.trimStart, trim_end: t.trimEnd }
        ),
        audioUrl: audio.url,
        audioVolume: audio.volume,
        audioFadeIn: audio.fadeIn,
        audioDuck: audio.duck,
      });
      let landed = false;
      // keep polling for up to 15 minutes: the old 3 minute window expired
      // right before real episodes landed, leaving the button missing forever
      for (let i = 0; i < 300; i++) {
        await new Promise((r) => setTimeout(r, 3000));
        const res = await download.refetch();
        if (res.data?.download_url || res.data?.url) {
          landed = true;
          setExportNotice(null);
          break;
        }
        if (i === 60) {
          setExportNotice(
            "Still rendering — long episodes can take a few more minutes. Leave this page open; the download appears here when the cut lands."
          );
        }
      }
      if (!landed) {
        setExportNotice(
          "The render is taking unusually long. Check that the Celery worker is running, then refresh this page."
        );
      }
    } catch (err) {
      setExportNotice(errText(err, "The render failed to start. Try again."));
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
      {/* a multi-episode drama cuts one episode at a time */}
      {multiEpisode && (
        <div className="flex flex-wrap items-center gap-1.5">
          {episodesPresent.map((ep) => (
            <button
              key={ep}
              onClick={() => setActiveEp(ep)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                currentEp === ep
                  ? "bg-primary/20 text-primary"
                  : "bg-white/[0.04] text-muted-foreground hover:text-foreground"
              }`}
            >
              Episode {ep}
            </button>
          ))}
          <span className="ml-2 text-[11px] text-muted-foreground">
            Each tab cuts and exports its episode as its own video.
          </span>
        </div>
      )}
      {/* live export progress: stitching, captions, mixing, uploading */}
      <LiveStageStrip
        projectId={projectId}
        stage="export"
        pending={rendering}
        fallback={[
          "Assembling the final cut",
          "Stitching clips and placing voices",
          "Burning captions into the picture",
          "Long episodes take a few minutes",
        ]}
      />
      {/* top: preview (left) + shot library (right) */}
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-2">
          {finalUrl && (
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setShowFinal(false)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  !showFinal
                    ? "bg-primary/20 text-primary"
                    : "bg-white/[0.04] text-muted-foreground hover:text-foreground"
                }`}
              >
                Editor preview
              </button>
              <button
                onClick={() => setShowFinal(true)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  showFinal
                    ? "bg-primary/20 text-primary"
                    : "bg-white/[0.04] text-muted-foreground hover:text-foreground"
                }`}
              >
                Final render
              </button>
              <span className="ml-1 text-[11px] text-muted-foreground">
                {showFinal
                  ? "The exported file: burned captions, mixed audio, fades."
                  : "Live preview with captions and voices; export follows this."}
              </span>
            </div>
          )}
          {showFinal && finalUrl ? (
            <div
              className={
                project?.video_ratio === "16:9"
                  ? "relative aspect-video w-full overflow-hidden rounded-2xl border hairline bg-black"
                  : "relative mx-auto aspect-[9/16] w-full max-w-[360px] overflow-hidden rounded-2xl border hairline bg-black"
              }
            >
              {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
              <video
                key={finalUrl}
                src={finalUrl}
                controls
                playsInline
                className="h-full w-full"
              />
            </div>
          ) : (
            <SequencePlayer
              items={timeline}
              index={selected}
              onIndexChange={selectClip}
              onDuration={handleDuration}
              onProgress={handleProgress}
              ratio={project?.video_ratio === "16:9" ? "16:9" : "9:16"}
              segments={segments}
            />
          )}
        </div>
        <ShotLibrary
          scenes={scenes}
          clipsByShot={clipsByShot}
          orphans={orphanClips}
          inTimeline={inTimeline}
          onAdd={addClip}
          onEdit={setEditingClip}
        />
      </div>

      {/* media bin */}
      <MediaBin
        media={media}
        onImport={handleImportMedia}
        onAdd={onAddAsset}
        uploading={uploadMedia.isPending || uploadAudio.isPending}
      />

      {/* bottom: timeline */}
      <EditorTimeline
        items={timeline}
        selectedIndex={selected}
        onSelect={selectClip}
        onReorder={setTimeline}
        onRemove={removeClip}
        onTrim={setTrimById}
        playheadSeconds={playhead}
        audio={audio}
        onAudioChange={setAudio}
        onAudioFile={handleAudioFile}
        onDropAsset={onAddAsset}
        audioUploading={uploadAudio.isPending}
      />

      {/* caption lane: every placed line at its real time, CapCut style */}
      {segments.some((s) => s.text) && totalSeconds > 0 && (
        <div className="rounded-xl border hairline bg-card p-3">
          <p className="mb-1.5 text-[10px] uppercase tracking-widest text-zinc-400">
            Captions · placed on the cut, exactly as they burn in
          </p>
          <div className="relative h-8 overflow-hidden rounded bg-white/[0.03]">
            {segments
              .filter((s) => s.text)
              .map((s, i) => (
                <span
                  key={i}
                  title={`${s.character ? s.character + ": " : ""}${s.text} · ${s.start.toFixed(1)}s`}
                  className="absolute bottom-1 top-1 overflow-hidden whitespace-nowrap rounded bg-sky-500/20 px-1.5 text-[10px] leading-6 text-sky-200"
                  style={{
                    left: `${(s.start / totalSeconds) * 100}%`,
                    width: `${Math.max(1.5, (s.duration / totalSeconds) * 100)}%`,
                  }}
                >
                  {s.text}
                </span>
              ))}
            <span
              className="absolute bottom-0 top-0 w-px bg-primary"
              style={{
                left: `${Math.min(100, (playhead / totalSeconds) * 100)}%`,
              }}
            />
          </div>
        </div>
      )}

      {/* export bar */}
      <div className="rounded-xl border hairline glass p-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="font-semibold">
            {multiEpisode ? `Export episode ${currentEp}` : "Export your cut"}
          </h2>
          <p className="text-sm text-muted-foreground">
            {multiEpisode
              ? `Renders episode ${currentEp}'s ${timeline.length} clips above into its own MP4.`
              : `Renders the ${timeline.length} clips above, in this order, into one MP4.`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {(result?.report_json?.episodes?.length ?? 0) > 1 ? (
            // a multi-episode drama delivers one video per episode
            result!.report_json!.episodes!.map((ep) => (
              <a key={ep.episode} href={ep.url} target="_blank" rel="noreferrer">
                <Button variant="outline">⬇ Episode {ep.episode}</Button>
              </a>
            ))
          ) : result?.download_url || result?.url ? (
            <a
              href={result.download_url || result.url || "#"}
              target="_blank"
              rel="noreferrer"
            >
              <Button variant="outline">⬇ Download MP4</Button>
            </a>
          ) : null}
          {result?.caption_url && (result?.report_json?.episodes?.length ?? 0) <= 1 ? (
            <a href={result.caption_url} target="_blank" rel="noreferrer">
              <Button variant="ghost" size="sm">
                .srt
              </Button>
            </a>
          ) : null}
          {(result?.report_json?.episodes?.length ?? 0) > 1 ? (
            <Button variant="ghost" size="sm" onClick={downloadAllZip}>
              ⬇ All (.zip)
            </Button>
          ) : null}
          {multiEpisode && (
            <Button
              variant="outline"
              onClick={() => handleExport(buildAllItems())}
              disabled={rendering}
              title="Renders every episode in one run, each as its own video"
            >
              Export all episodes
            </Button>
          )}
          <Button
            onClick={() => handleExport()}
            disabled={rendering || timeline.length === 0}
            className="glow"
            size="lg"
          >
            {rendering
              ? "Rendering…"
              : multiEpisode
                ? `🎬 Export episode ${currentEp}`
                : "🎬 Export final MP4"}
          </Button>
        </div>
      </div>

      {exportNotice && (
        <p className="rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
          {exportNotice}
        </p>
      )}

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
            <Stat label="Clips" value={String(result.report_json.total_clips ?? 0)} />
            <Stat
              label="Video cost"
              value={`$${(result.report_json.video_cost_usd ?? 0).toFixed(2)}`}
            />
            <Stat
              label="Grand total"
              value={`$${(result.report_json.grand_total_cost ?? 0).toFixed(2)} / $${result.report_json.budget_usd ?? "—"}`}
            />
          </div>
        </div>
      ) : null}

      <ClipEditModal
        clip={editingClip}
        projectId={projectId}
        label={editingClip ? shotLabel[editingClip.shot_id] : undefined}
        onClose={() => setEditingClip(null)}
      />
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
