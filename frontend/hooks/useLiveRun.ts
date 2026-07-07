"use client";

import { useEffect, useMemo } from "react";
import { create } from "zustand";
import { getSocket } from "@/lib/websocket";

/** ── ONE live-run store for the whole project session ────────────────────
 * The Showrunner chat's typing bubbles, the dock's crew micro-status and the
 * crew modal's pipeline all read THIS store. It subscribes to the shared
 * socket exactly once per project, so every surface shows the same run state
 * at the same moment — they can never drift apart.
 */

/** The five pipeline stages, matching PipelineNav / GET /progress. */
export const STAGE_ORDER = [
  "script",
  "characters",
  "storyboard",
  "generate",
  "export",
] as const;
export type StageKey = (typeof STAGE_ORDER)[number];

export const STAGE_LABELS: Record<StageKey, string> = {
  script: "Script",
  characters: "Characters",
  storyboard: "Storyboard",
  generate: "Generate",
  export: "Edit & Export",
};

/** Raw stage:progress keys → pipeline stage (relationships ride under Characters). */
export const RAW_TO_STAGE: Record<string, StageKey> = {
  script: "script",
  characters: "characters",
  relationships: "characters",
  storyboard: "storyboard",
  generate: "generate",
  export: "export",
};

/** LangGraph node → friendly copy (chat lines) and parent pipeline stage. */
export const NODE_LABELS: Record<string, string> = {
  generate_script: "Writing script",
  judge: "Judging quality",
  revise: "Revising with the judge's notes",
  extract_characters: "Extracting characters",
  clarify: "Checking for ambiguity",
  storyboard: "Storyboarding",
  casting: "Casting",
  audio: "Voicing dialogue",
  budget: "Fitting the budget",
  generate_video: "Dispatching video",
  finalize: "Finalizing the plan",
};
const NODE_TO_STAGE: Record<string, StageKey> = {
  generate_script: "script",
  judge: "script",
  revise: "script",
  extract_characters: "characters",
  clarify: "characters",
  storyboard: "storyboard",
  casting: "generate",
  audio: "generate",
  budget: "generate",
  generate_video: "generate",
  finalize: "generate",
};

/** One stage:progress event from the backend. */
export interface StageProgress {
  stage: string;
  status: "started" | "update" | "completed" | "failed";
  agent?: string;
  label: string;
  index?: number;
  total?: number;
}

export interface RunningStage {
  stage: string;
  agent: string;
  label: string;
  since: number;
  index?: number;
  total?: number;
}

export interface TrailEntry {
  at: number;
  agent: string;
  label: string;
  kind: "run" | "done" | "warn" | "fail";
}

export interface FinishedEvent {
  agent: string;
  label: string;
  failed: boolean;
}

interface LiveRunState {
  projectId: string | null;
  /** live "who is working" keyed by RAW stage (chat shows relationships separately) */
  running: Record<string, RunningStage>;
  /** per-pipeline-stage event log for the crew modal, this session (capped) */
  trail: Record<StageKey, TrailEntry[]>;
  /** last failure label per stage — cleared when the stage starts again */
  failed: Partial<Record<StageKey, string>>;
}

const emptyTrail = (): Record<StageKey, TrailEntry[]> => ({
  script: [],
  characters: [],
  storyboard: [],
  generate: [],
  export: [],
});

export const useLiveRunStore = create<LiveRunState>(() => ({
  projectId: null,
  running: {},
  trail: emptyTrail(),
  failed: {},
}));

const TRAIL_CAP = 30;

function pushTrail(stage: StageKey, entry: TrailEntry) {
  useLiveRunStore.setState((s) => ({
    trail: {
      ...s.trail,
      [stage]: [...s.trail[stage], entry].slice(-TRAIL_CAP),
    },
  }));
}

function upsertRunning(
  rawStage: string,
  patch: { agent?: string; label: string; index?: number; total?: number }
) {
  useLiveRunStore.setState((s) => ({
    running: {
      ...s.running,
      [rawStage]: {
        stage: rawStage,
        agent: patch.agent ?? "Agent",
        label: patch.label,
        since: s.running[rawStage]?.since ?? Date.now(),
        index: patch.index,
        total: patch.total,
      },
    },
  }));
}

function clearRunning(rawStage: string) {
  useLiveRunStore.setState((s) => {
    if (!(rawStage in s.running)) return s;
    const next = { ...s.running };
    delete next[rawStage];
    return { running: next };
  });
}

function setFailed(stage: StageKey, label: string | null) {
  useLiveRunStore.setState((s) => {
    const failed = { ...s.failed };
    if (label === null) delete failed[stage];
    else failed[stage] = label;
    return { failed };
  });
}

/* Completed/failed announcements → the Showrunner chat turns these into
 * bubbles. Kept as a plain pub/sub so the chat's message ids stay local. */
type FinishedCb = (m: FinishedEvent) => void;
const finishedSubs = new Set<FinishedCb>();
export function subscribeFinished(cb: FinishedCb): () => void {
  finishedSubs.add(cb);
  return () => {
    finishedSubs.delete(cb);
  };
}

let wiredFor: string | null = null;
let offFns: (() => void)[] = [];

/** Idempotent: wires the socket handlers once per project. Everything that
 * displays live run state calls this — the store outlives any one panel. */
export function ensureLiveRun(projectId: string) {
  if (!projectId || wiredFor === projectId) return;
  offFns.forEach((f) => f());
  offFns = [];
  wiredFor = projectId;
  useLiveRunStore.setState({
    projectId,
    running: {},
    trail: emptyTrail(),
    failed: {},
  });

  const socket = getSocket();
  socket.connect();
  socket.emit("join_project", { project_id: projectId });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const on = (event: string, handler: (p: any) => void) => {
    socket.on(event, handler);
    offFns.push(() => socket.off(event, handler));
  };

  // ── the canonical per-stage protocol ──
  on("stage:progress", (p: StageProgress) => {
    if (!p?.stage) return;
    const mapped = RAW_TO_STAGE[p.stage];
    const agent = p.agent ?? "Agent";
    if (p.status === "started" || p.status === "update") {
      upsertRunning(p.stage, p);
      if (mapped) {
        if (p.status === "started") setFailed(mapped, null);
        pushTrail(mapped, { at: Date.now(), agent, label: p.label, kind: "run" });
      }
    } else {
      clearRunning(p.stage);
      const failed = p.status === "failed";
      if (mapped) {
        pushTrail(mapped, {
          at: Date.now(),
          agent,
          label: p.label,
          kind: failed ? "fail" : "done",
        });
        if (failed) setFailed(mapped, p.label);
      }
      finishedSubs.forEach((cb) => cb({ agent, label: p.label, failed }));
    }
  });

  // ── auto-run node hops feed the trail (chat renders its own copy of these) ──
  on("agent:node", (d: { node?: string }) => {
    const stage = d?.node ? NODE_TO_STAGE[d.node] : undefined;
    const label = d?.node ? NODE_LABELS[d.node] : undefined;
    if (!stage || !label) return;
    pushTrail(stage, { at: Date.now(), agent: "Showrunner", label, kind: "run" });
  });

  /* ── synthesis: casting/generation/export activity events become Generate
   * and Export run-state, so those stages are live in the SAME store even
   * though the backend narrates them on their own event names.
   * NOTE: these never call finishedSubs — the chat already turns them into
   * messages via its activity feed, and doubling would duplicate bubbles.
   * TODO(data): the backend does not emit retry-count events today; when it
   * does ("retrying 2/3"), surface them here as kind:"warn" trail entries. */
  const gen = (agent: string, label: string) =>
    upsertRunning("generate", { agent, label });

  on("casting.started", () => {
    gen("Casting", "Casting the production bible");
    pushTrail("generate", {
      at: Date.now(),
      agent: "Casting",
      label: "Casting the production bible",
      kind: "run",
    });
  });
  on("casting.wardrobe_plan.completed", (p) => {
    pushTrail("generate", {
      at: Date.now(),
      agent: "Casting",
      label: `Wardrobe planned: ${p?.variant_count ?? "?"} outfit(s)`,
      kind: "done",
    });
  });
  on("casting.plate.started", () => gen("Casting", "Shooting reference plates"));
  on("casting.plate.completed", (p) => {
    const what = `Plate ready: ${p?.kind ?? "plate"} ${String(p?.key ?? "").replace(/_/g, " ")}`.trim();
    gen("Casting", what);
    pushTrail("generate", { at: Date.now(), agent: "Casting", label: what, kind: "done" });
  });
  on("casting.awaiting_review", () => {
    clearRunning("generate");
    pushTrail("generate", {
      at: Date.now(),
      agent: "Casting",
      label: "Casting paused, awaiting your review",
      kind: "warn",
    });
  });
  on("casting.completed", (p) => {
    clearRunning("generate");
    pushTrail("generate", {
      at: Date.now(),
      agent: "Casting",
      label: p?.auto_approved ? "Bible cast and auto approved" : "Bible cast, awaiting your review",
      kind: "done",
    });
  });
  on("budget:fitted", (p) => {
    pushTrail("generate", {
      at: Date.now(),
      agent: "Producer",
      label: `Plan fitted under $${p?.cap ?? "?"}${p?.deferred ? ` · ${p.deferred} deferred` : ""}`,
      kind: "done",
    });
  });
  on("generation.shot.started", (p) => {
    const label = `Rendering scene ${p?.scene_number ?? "?"} shot ${p?.shot_number ?? "?"}`;
    gen("Renderer", label);
    pushTrail("generate", { at: Date.now(), agent: "Renderer", label, kind: "run" });
  });
  on("generation.shot.completed", (p) => {
    const ok = p?.status === "APPROVED";
    pushTrail("generate", {
      at: Date.now(),
      agent: "Renderer",
      label: `Scene ${p?.scene_number ?? "?"} shot ${p?.shot_number ?? "?"} rendered${ok ? "" : ", flagged for review"}`,
      kind: ok ? "done" : "warn",
    });
  });
  on("continuity.scoring.started", () => gen("Continuity", "Scoring the take for face and scene drift"));
  on("continuity.flagged", (p) => {
    pushTrail("generate", {
      at: Date.now(),
      agent: "Continuity",
      label: `Continuity flagged a clip at ${p?.continuity_score ?? "?"}%`,
      kind: "warn",
    });
  });
  on("job:completed", (p) => {
    clearRunning("generate");
    pushTrail("generate", {
      at: Date.now(),
      agent: "Renderer",
      label: `All clips rendered: ${p?.total_clips ?? "?"} clip(s) for $${p?.total_cost ?? "?"}`,
      kind: "done",
    });
  });
  on("job:budget_exhausted", () => {
    clearRunning("generate");
    pushTrail("generate", {
      at: Date.now(),
      agent: "Producer",
      label: "Stopped at the spend cap, review what rendered",
      kind: "warn",
    });
  });
  on("job:blocked", (p) => {
    clearRunning("generate");
    const label = `Generation blocked: ${(p?.issues ?? []).join("; ") || "pre-flight failed"}`;
    pushTrail("generate", { at: Date.now(), agent: "Producer", label, kind: "fail" });
    setFailed("generate", label);
  });

  // export sub-steps arrive as stage:progress from the worker; the audio mix
  // still narrates on its own event names
  on("audio.mix.started", () => {
    upsertRunning("export", { agent: "Audio Mixer", label: "Mixing dialogue and music" });
    pushTrail("export", {
      at: Date.now(),
      agent: "Audio Mixer",
      label: "Mixing dialogue and music",
      kind: "run",
    });
  });
  on("audio.mix.completed", () => {
    pushTrail("export", { at: Date.now(), agent: "Audio Mixer", label: "Audio mix ready", kind: "done" });
  });
  on("export.completed", () => {
    clearRunning("export");
  });
}

/** One live entry per pipeline stage (relationships fold under Characters). */
export function mapActiveByStage(
  running: RunningStage[]
): Partial<Record<StageKey, RunningStage>> {
  const map: Partial<Record<StageKey, RunningStage>> = {};
  for (const r of running) {
    const k = RAW_TO_STAGE[r.stage];
    if (k && !map[k]) map[k] = r;
  }
  return map;
}

/** Live "who is working right now" — the shared store behind every surface. */
export function useRunningStages(projectId: string): RunningStage[] {
  useEffect(() => {
    ensureLiveRun(projectId);
  }, [projectId]);
  const running = useLiveRunStore((s) => s.running);
  return useMemo(() => Object.values(running), [running]);
}
