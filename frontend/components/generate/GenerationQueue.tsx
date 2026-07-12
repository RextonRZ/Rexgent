"use client";

import { useMemo } from "react";
import { useGenerationStore } from "@/stores/generationStore";
import { useStoryboard, type SceneShots } from "@/hooks/useStoryboard";
import { useLatestJobClips } from "@/hooks/useClips";
import { useLatestJobLive } from "@/hooks/useGeneration";
import { useProject } from "@/hooks/useProjects";
import { clipStatusChip } from "@/lib/clipStatus";
import type { ClipReference, Shot } from "@/lib/types";

interface Tile {
  url?: string;
  status: string;
  score?: number | null;
  refs?: ClipReference[] | null;
}

const REF_LABELS: Record<ClipReference["role"], string> = {
  identity: "identity plate",
  costume: "costume plate",
  prev_frame: "previous shot frame",
  scene_anchor: "scene anchor frame",
  location: "location plate",
  style: "style plate",
};

/** The consistency engine, provable: the exact bible references this clip
 * was conditioned on, in the order they were sent to the video model. */
function ReferenceStrip({ refs }: { refs: ClipReference[] }) {
  return (
    <div className="mt-2 flex items-center gap-1">
      <span className="mr-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
        refs
      </span>
      {refs.map((r, i) => (
        <img
          key={`${r.url}-${i}`}
          src={r.url}
          alt={REF_LABELS[r.role] ?? r.role}
          title={`${REF_LABELS[r.role] ?? r.role}${r.character ? ` · ${r.character}` : ""}`}
          loading="lazy"
          className="h-7 w-7 rounded border hairline object-cover"
        />
      ))}
    </div>
  );
}

interface SceneBlock {
  scene: SceneShots;
  shots: Shot[];
}

export function GenerationQueue({ projectId }: { projectId: string }) {
  const live = useGenerationStore((s) => s.clips);
  const { data: storyboard } = useStoryboard(projectId);
  const { data: persisted } = useLatestJobClips(projectId);
  const { data: latestJob } = useLatestJobLive(projectId);
  const { data: project } = useProject(projectId);
  const scenes = storyboard?.scenes ?? [];
  const multiEpisode =
    new Set(scenes.map((s) => s.episode ?? 1)).size > 1;
  // frame the tiles the way THIS drama renders — vertical unless 16:9 was picked
  const vertical = project?.video_ratio !== "16:9";
  const mediaBox = vertical ? "relative aspect-[9/16] bg-black" : "relative aspect-video bg-black";

  // Merge persisted clips (survive navigation/refresh) with the live progress store.
  const byShot = useMemo(() => {
    const map: Record<string, Tile> = {};
    // 1) best persisted take per shot (APPROVED first, then highest score)
    for (const c of persisted?.clips ?? []) {
      if (!c.url) continue;
      const cur = map[c.shot_id];
      const better =
        !cur ||
        (c.status === "APPROVED" && cur.status !== "APPROVED") ||
        (c.consistency_score ?? 0) > (cur.score ?? 0);
      if (better)
        map[c.shot_id] = {
          url: c.url,
          status: c.status,
          score: c.consistency_score,
          refs: c.references_json,
        };
    }
    // 2) overlay live progress (a shot mid-generation wins)
    for (const [sid, cp] of Object.entries(live)) {
      map[sid] = {
        url: cp.clip_url ?? map[sid]?.url,
        status: cp.status,
        score: cp.consistency_score ?? map[sid]?.score,
        refs: map[sid]?.refs,
      };
    }
    // 3) a RUNNING job means every unrendered shot is queued or rendering —
    // show the dreaming tile even after a refresh wiped the live store,
    // so the page never reads as "nothing happening" mid-run
    if (latestJob?.status === "RUNNING" || latestJob?.status === "PENDING") {
      for (const scene of scenes) {
        for (const sh of scene.shots) {
          if (!map[sh.id]) map[sh.id] = { url: undefined, status: "GENERATING" };
        }
      }
    }
    return map;
  }, [persisted, live, latestJob, scenes]);

  const hasAny = Object.keys(byShot).length > 0;
  if (!hasAny) {
    return (
      <p className="text-center text-muted-foreground py-8">
        No clips yet. Start generation to watch progress live.
      </p>
    );
  }

  // Clips whose shot no longer exists (storyboard was regenerated) still show,
  // under "Earlier takes" — old videos never silently disappear.
  const currentShotIds = new Set(
    scenes.flatMap((s) => s.shots.map((sh) => sh.id))
  );
  const orphans = Object.entries(byShot).filter(
    ([sid, t]) => !currentShotIds.has(sid) && t.url
  );

  // Scenes with clips; consecutive single-clip scenes pair up two per row.
  const blocks: SceneBlock[] = scenes
    .map((scene) => ({
      scene,
      shots: scene.shots.filter((sh) => byShot[sh.id]),
    }))
    .filter((b) => b.shots.length > 0);

  const rows: SceneBlock[][] = [];
  let run: SceneBlock[] = [];
  for (const b of blocks) {
    if (b.shots.length === 1) {
      run.push(b);
    } else {
      if (run.length) {
        rows.push(run);
        run = [];
      }
      rows.push([b]);
    }
  }
  if (run.length) rows.push(run);

  /** The render-in-progress tile, Qwen studio style: a soft violet cloud
 * drifting behind a white pill — waiting reads as dreaming, not hanging. */
function DreamingTile({ checking }: { checking: boolean }) {
  return (
    <div
      className="flex h-full w-full flex-col items-center justify-center gap-2.5 motion-safe:animate-[dream-drift_9s_ease-in-out_infinite]"
      style={{
        background:
          "linear-gradient(130deg, #6d28d9 0%, #a78bfa 30%, #c4b5fd 50%, #8b5cf6 72%, #5b21b6 100%)",
        backgroundSize: "300% 300%",
      }}
    >
      <span className="flex items-center gap-2 rounded-full bg-white px-4 py-1.5 shadow-lg">
        <span className="h-2 w-2 rounded-full bg-violet-500 motion-safe:animate-pulse" />
        <span className="bg-gradient-to-r from-violet-600 to-fuchsia-500 bg-clip-text text-sm font-semibold text-transparent">
          {checking ? "Checking…" : "Dreaming…"}
        </span>
      </span>
      <span className="text-[11px] text-white/85 drop-shadow">
        {checking
          ? "Scoring continuity on the fresh take"
          : "This usually takes a few minutes"}
      </span>
    </div>
  );
}

const renderTile = (shot: Shot) => {
    const tile = byShot[shot.id];
    const chip = clipStatusChip(tile.status);
    const score = tile.score;
    return (
      <div key={shot.id} className="rounded-xl border hairline bg-card overflow-hidden">
        {/* media box follows the drama's delivery format so clips fill the frame
            they were generated for (portrait for 9:16, widescreen for 16:9) */}
        <div className={mediaBox}>
          {tile.url ? (
            <video
              src={`${tile.url}#t=0.1`}
              controls muted
              playsInline
              preload="metadata"
              className="h-full w-full object-contain bg-black"
            />
          ) : tile.status === "GENERATING" || tile.status === "CHECKING" ? (
            <DreamingTile checking={tile.status === "CHECKING"} />
          ) : (
            <div className="h-full w-full flex items-center justify-center text-xs text-muted-foreground">
              {tile.status.toLowerCase()}
            </div>
          )}
          {/* badges live at the top — the bottom belongs to the video controls */}
          <div className="absolute top-2 left-2 flex items-center gap-1.5">
            <span className="rounded bg-black/60 px-2 py-0.5 text-[11px] font-semibold text-white">
              Shot {shot.number}
              {shot.shot_type ? ` · ${shot.shot_type}` : ""}
            </span>
            {typeof score === "number" && (
              <span
                className={`rounded bg-black/60 px-1.5 py-0.5 text-[10px] font-bold ${
                  score >= 70 ? "text-ok" : "text-warn"
                }`}
              >
                ID {score}%
              </span>
            )}
          </div>
          <span
            className={`absolute top-2 right-2 rounded-full px-2 py-0.5 text-[10px] ${chip.cls}`}
          >
            {chip.label}
          </span>
        </div>
        <div className="p-3">
          {shot.action && (
            <p className="text-xs text-foreground line-clamp-2">{shot.action}</p>
          )}
          {shot.dialogue && (
            <p className="mt-1 text-[11px] italic text-primary/80 line-clamp-1">
              “{shot.dialogue}”
            </p>
          )}
          {tile.refs && tile.refs.length > 0 && <ReferenceStrip refs={tile.refs} />}
        </div>
      </div>
    );
  };

  const renderBlock = (block: SceneBlock, paired: boolean) => (
    <div key={block.scene.scene_number}>
      <div className="flex items-center gap-2 mb-3 text-sm">
        {multiEpisode && (
          <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-semibold text-primary">
            EP {block.scene.episode ?? 1}
          </span>
        )}
        <span className="font-semibold">Scene {block.scene.scene_number}</span>
        {block.scene.heading && (
          <span className="text-muted-foreground truncate">
            — {block.scene.heading}
          </span>
        )}
      </div>
      <div className={paired ? "grid gap-4" : "grid gap-4 md:grid-cols-2"}>
        {block.shots.map(renderTile)}
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      <p className="text-[11px] text-muted-foreground">
        Previews play muted: raw takes carry the video model&apos;s own
        placeholder sound, sometimes fake chatter in another language. It is
        replaced at export, where your cast&apos;s real voices and captions go
        on. Unmute a tile only to check ambience.
      </p>
      {rows.map((row, i) =>
        row.length > 1 ? (
          <div key={`row-${i}`} className="grid gap-6 md:grid-cols-2 items-start">
            {row.map((b) => renderBlock(b, true))}
          </div>
        ) : (
          renderBlock(row[0], false)
        )
      )}

      {orphans.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3 text-sm">
            <span className="font-semibold">Earlier takes</span>
            <span className="text-xs text-muted-foreground">
              — from previous storyboards
            </span>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {orphans.map(([sid, tile]) => {
              const chip = clipStatusChip(tile.status);
              return (
                <div
                  key={sid}
                  className="rounded-xl border hairline bg-card overflow-hidden"
                >
                  <div className={mediaBox}>
                    <video
                      src={`${tile.url}#t=0.1`}
                      controls muted
                      playsInline
                      preload="metadata"
                      className="h-full w-full object-contain bg-black"
                    />
                    <div className="absolute top-2 left-2 flex items-center gap-1.5">
                      {typeof tile.score === "number" && (
                        <span
                          className={`rounded bg-black/60 px-1.5 py-0.5 text-[10px] font-bold ${
                            tile.score >= 70 ? "text-ok" : "text-warn"
                          }`}
                        >
                          ID {tile.score}%
                        </span>
                      )}
                    </div>
                    <span
                      className={`absolute top-2 right-2 rounded-full px-2 py-0.5 text-[10px] ${chip.cls}`}
                    >
                      {chip.label}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
