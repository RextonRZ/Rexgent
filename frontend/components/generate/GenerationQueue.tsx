"use client";

import { useMemo } from "react";
import { useGenerationStore } from "@/stores/generationStore";
import { useStoryboard, type SceneShots } from "@/hooks/useStoryboard";
import { useLatestJobClips } from "@/hooks/useClips";
import { clipStatusChip } from "@/lib/clipStatus";
import type { Shot } from "@/lib/types";

interface Tile {
  url?: string;
  status: string;
  score?: number | null;
}

interface SceneBlock {
  scene: SceneShots;
  shots: Shot[];
}

export function GenerationQueue({ projectId }: { projectId: string }) {
  const live = useGenerationStore((s) => s.clips);
  const { data: storyboard } = useStoryboard(projectId);
  const { data: persisted } = useLatestJobClips(projectId);
  const scenes = storyboard?.scenes ?? [];

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
      if (better) map[c.shot_id] = { url: c.url, status: c.status, score: c.consistency_score };
    }
    // 2) overlay live progress (a shot mid-generation wins)
    for (const [sid, cp] of Object.entries(live)) {
      map[sid] = {
        url: cp.clip_url ?? map[sid]?.url,
        status: cp.status,
        score: cp.consistency_score ?? map[sid]?.score,
      };
    }
    return map;
  }, [persisted, live]);

  const hasAny = Object.keys(byShot).length > 0;
  if (!hasAny) {
    return (
      <p className="text-center text-muted-foreground py-8">
        No clips yet. Start generation to watch progress live.
      </p>
    );
  }

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

  const renderTile = (shot: Shot) => {
    const tile = byShot[shot.id];
    const chip = clipStatusChip(tile.status);
    const score = tile.score;
    return (
      <div key={shot.id} className="rounded-xl border hairline bg-card overflow-hidden">
        <div className="relative aspect-video bg-black">
          {tile.url ? (
            <video
              src={`${tile.url}#t=0.1`}
              controls
              playsInline
              preload="metadata"
              className="h-full w-full object-contain bg-black"
            />
          ) : (
            <div className="h-full w-full flex items-center justify-center text-xs text-muted-foreground">
              {tile.status === "GENERATING" || tile.status === "CHECKING"
                ? "rendering…"
                : tile.status.toLowerCase()}
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
        </div>
      </div>
    );
  };

  const renderBlock = (block: SceneBlock, paired: boolean) => (
    <div key={block.scene.scene_number}>
      <div className="flex items-center gap-2 mb-3 text-sm">
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
      {rows.map((row, i) =>
        row.length > 1 ? (
          <div key={`row-${i}`} className="grid gap-6 md:grid-cols-2 items-start">
            {row.map((b) => renderBlock(b, true))}
          </div>
        ) : (
          renderBlock(row[0], false)
        )
      )}
    </div>
  );
}
