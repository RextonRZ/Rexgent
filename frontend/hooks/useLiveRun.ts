"use client";

import { useEffect, useMemo } from "react";
import { create } from "zustand";
import { getSocket } from "@/lib/websocket";
import { useLatestJobLive } from "./useGeneration";

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
  export: "Export",
};

/** Raw stage:progress keys → pipeline stage (relationships ride under Characters). */
export const RAW_TO_STAGE: Record<string, StageKey> = {
  script: "script",
  characters: "characters",
  relationships: "characters",
  casting: "characters",
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
  casting: "characters",
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
  /** true when only tool:progress events created this entry — such entries
   * self-clear when their last tool finishes (a standalone budget fit must
   * not spin forever); stage-level events own their clearing. */
  fromTool?: boolean;
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

/** One tool node inside a stage's sub-graph — driven by `tool:progress`. */
export interface ToolState {
  tool: string;
  status: "run" | "done" | "fail";
  agent?: string;
  /** what flowed out of the tool, shown on its edge ("8 shots", "5 plates") */
  artifact?: string;
  error?: string;
  index?: number;
  total?: number;
  since: number;
  at: number;
}

interface LiveRunState {
  projectId: string | null;
  /** live "who is working" keyed by RAW stage (chat shows relationships separately) */
  running: Record<string, RunningStage>;
  /** per-pipeline-stage event log for the crew modal, this session (capped) */
  trail: Record<StageKey, TrailEntry[]>;
  /** last failure label per stage — cleared when the stage starts again */
  failed: Partial<Record<StageKey, string>>;
  /** per-stage tool nodes (the modal's level-2 graph); latest state per tool.
   * Deliberately NOT reset on stage start: a re-run overwrites each tool as it
   * fires again, and finished sub-paths stay reviewable. */
  tools: Record<StageKey, Record<string, ToolState>>;
}

const emptyTrail = (): Record<StageKey, TrailEntry[]> => ({
  script: [],
  characters: [],
  storyboard: [],
  generate: [],
  export: [],
});

const emptyTools = (): Record<StageKey, Record<string, ToolState>> => ({
  script: {},
  characters: {},
  storyboard: {},
  generate: {},
  export: {},
});

export const useLiveRunStore = create<LiveRunState>(() => ({
  projectId: null,
  running: {},
  trail: emptyTrail(),
  failed: {},
  tools: emptyTools(),
}));

const TRAIL_CAP = 30;

// Tools that run as fast background pre-fits (the budget allocator fits the plan
// the moment the storyboard lands). They stay visible in the crew graph but never
// spin a chat bubble — a lingering "budget allocate" spinner reads as "stuck".
const QUIET_TOOLS = new Set(["budget_allocate"]);

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
  patch: {
    agent?: string;
    label: string;
    index?: number;
    total?: number;
    fromTool?: boolean;
  }
) {
  useLiveRunStore.setState((s) => {
    const existing = s.running[rawStage];
    return {
      running: {
        ...s.running,
        [rawStage]: {
          stage: rawStage,
          agent: patch.agent ?? "Agent",
          label: patch.label,
          since: existing?.since ?? Date.now(),
          index: patch.index,
          total: patch.total,
          // a stage-level event (fromTool undefined) claims ownership; a
          // tool event never overrides that claim
          fromTool:
            patch.fromTool === undefined
              ? false
              : (existing?.fromTool ?? patch.fromTool),
        },
      },
    };
  });
}

function clearRunning(rawStage: string) {
  useLiveRunStore.setState((s) => {
    if (!(rawStage in s.running)) return s;
    const next = { ...s.running };
    delete next[rawStage];
    return { running: next };
  });
}

/** Self-heal: drop every running spinner whose pipeline stage the backend now
 * reports as FINISHED. A spinner normally clears on a live "done" websocket
 * event, which a dropped socket message or a backgrounded tab can miss — this
 * reconciles against real status so a finished stage can never spin forever. */
export function clearFinishedStage(stage: StageKey) {
  useLiveRunStore.setState((s) => {
    let changed = false;
    const next: Record<string, RunningStage> = {};
    for (const [rawKey, r] of Object.entries(s.running)) {
      if (RAW_TO_STAGE[rawKey] === stage) {
        changed = true;
        continue;
      }
      next[rawKey] = r;
    }
    return changed ? { running: next } : s;
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

/** A finished stage cannot have a spinning tool: any tool still "run" when
 * its stage completes flips to done (or fail) — a dropped websocket event
 * can no longer leave an eternal spinner. */
function settleStageTools(stage: StageKey, failed: boolean) {
  useLiveRunStore.setState((s) => {
    const current = s.tools[stage];
    if (!Object.values(current).some((t) => t.status === "run")) return s;
    const next: Record<string, ToolState> = {};
    for (const [k, v] of Object.entries(current)) {
      next[k] =
        v.status === "run"
          ? { ...v, status: failed ? "fail" : "done", at: Date.now() }
          : v;
    }
    return { tools: { ...s.tools, [stage]: next } };
  });
}

/** `tool:progress` payload from the backend (see app/websocket/tool_events.py). */
export interface ToolProgress {
  stage: string;
  tool: string;
  status: "started" | "succeeded" | "failed";
  agent?: string;
  artifact?: string;
  error?: string;
  index?: number;
  total?: number;
}

function upsertTool(p: ToolProgress) {
  const stage = p.stage as StageKey;
  if (!STAGE_ORDER.includes(stage) || !p.tool) return;
  useLiveRunStore.setState((s) => {
    const prev = s.tools[stage][p.tool];
    const next: ToolState = {
      tool: p.tool,
      status:
        p.status === "succeeded" ? "done" : p.status === "failed" ? "fail" : "run",
      agent: p.agent ?? prev?.agent,
      // a succeeded event without an artifact keeps the last known one
      artifact: p.artifact ?? prev?.artifact,
      error: p.status === "failed" ? p.error : undefined,
      index: p.index ?? (p.status === "started" ? prev?.index : undefined),
      total: p.total ?? prev?.total,
      since: p.status === "started" && prev?.status === "run" ? prev.since : Date.now(),
      at: Date.now(),
    };
    return {
      tools: { ...s.tools, [stage]: { ...s.tools[stage], [p.tool]: next } },
    };
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
    tools: emptyTools(),
  });

  const socket = getSocket();
  socket.connect();
  socket.emit("join_project", { project_id: projectId });

  // hydrate the crew graph from the server snapshot: green ticks survive
  // refresh and dock re-opens; a dropped websocket event can't fake "idle"
  import("@/lib/api").then(({ default: api }) =>
    api
      .get(`/api/agent/${projectId}/tools`)
      .then(({ data }) => {
        const snap = (data?.tools ?? {}) as Record<
          string,
          Record<string, ToolProgress>
        >;
        useLiveRunStore.setState((s) => {
          const tools = { ...s.tools };
          for (const stage of Object.keys(snap)) {
            if (!STAGE_ORDER.includes(stage as StageKey)) continue;
            const sk = stage as StageKey;
            const merged = { ...tools[sk] };
            for (const [tool, ev] of Object.entries(snap[stage])) {
              if (merged[tool]) continue; // live events win over the snapshot
              merged[tool] = {
                tool,
                status:
                  ev.status === "succeeded"
                    ? "done"
                    : ev.status === "failed"
                      ? "fail"
                      : "run",
                agent: ev.agent,
                artifact: ev.artifact,
                error: ev.error,
                index: ev.index,
                total: ev.total,
                since: Date.now(),
                at: Date.now(),
              };
            }
            tools[sk] = merged;
          }
          return { tools };
        });
      })
      .catch(() => {})
  );
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
        settleStageTools(mapped, failed);
      }
      finishedSubs.forEach((cb) => cb({ agent, label: p.label, failed }));
    }
  });

  // ── the per-TOOL protocol: each stage's machinery ticks individually in
  // the crew modal's workflow graph — AND keeps the stage lit in real time.
  // Generate spends whole minutes in synth/fit/preflight before its first
  // shot event; without this the dock sat on "Crew idle" the entire time. ──
  on("tool:progress", (p: ToolProgress) => {
    if (!p?.stage || !p?.tool) return;
    upsertTool(p);
    // Quiet background tools (the storyboard-time budget pre-fit) belong in the
    // crew graph but must NOT spawn a "Producer working" chat spinner — it bleeds
    // into the Storyboard->Generate flow and can linger after it finishes.
    if (QUIET_TOOLS.has(p.tool)) return;
    const terminal = p.status !== "started";
    const existing = useLiveRunStore.getState().running[p.stage];
    // A terminal tool event must never BIRTH a bubble: event order across the
    // worker's pubsub isn't guaranteed, and a trailing "succeeded" arriving
    // after the stage already completed used to resurrect a ghost spinner
    // ("dispatch video done" ticking forever). It also never overwrites
    // stage-level narration — only tool-owned entries take the "done" label.
    if (!terminal || existing?.fromTool) {
      const verb =
        p.status === "succeeded" ? " done" : p.status === "failed" ? " failed" : "";
      if (!terminal || existing) {
        upsertRunning(p.stage, {
          agent: p.agent ?? "Crew",
          label: `${p.tool.replace(/_/g, " ")}${verb}`,
          index: p.index,
          total: p.total,
          fromTool: true,
        });
      }
    }
    // tool-only entries self-clear once their stage has no tool running —
    // a standalone budget fit must not leave the stage spinning forever
    if (terminal) {
      const s = useLiveRunStore.getState();
      const entry = s.running[p.stage];
      const anyToolRunning = Object.values(
        s.tools[p.stage as StageKey] ?? {}
      ).some((t) => t.status === "run");
      if (entry?.fromTool && !anyToolRunning) clearRunning(p.stage);
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
  const castingRun = (agent: string, label: string) =>
    upsertRunning("casting", { agent, label });

  on("casting.started", () => {
    castingRun("Casting", "Casting the production bible");
    pushTrail("characters", {
      at: Date.now(),
      agent: "Casting",
      label: "Casting the production bible",
      kind: "run",
    });
  });
  on("casting.wardrobe_plan.completed", (p) => {
    pushTrail("characters", {
      at: Date.now(),
      agent: "Casting",
      label: `Wardrobe planned: ${p?.variant_count ?? "?"} outfit(s)`,
      kind: "done",
    });
  });
  on("casting.plate.started", () => castingRun("Casting", "Shooting reference plates"));
  on("casting.plate.completed", (p) => {
    const what = `Plate ready: ${p?.kind ?? "plate"} ${String(p?.key ?? "").replace(/_/g, " ")}`.trim();
    castingRun("Casting", what);
    pushTrail("characters", { at: Date.now(), agent: "Casting", label: what, kind: "done" });
  });
  on("casting.awaiting_review", () => {
    clearRunning("casting");
    pushTrail("characters", {
      at: Date.now(),
      agent: "Casting",
      label: "Casting paused, awaiting your review",
      kind: "warn",
    });
  });
  on("casting.completed", (p) => {
    clearRunning("casting");
    pushTrail("characters", {
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
    settleStageTools("generate", false);
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
  // Self-heal the Generate spinner against the authoritative job status: the
  // live job query polls while RUNNING/PENDING and lands on the terminal status
  // (COMPLETE / BUDGET_EXHAUSTED / BLOCKED), clearing any generate spinner that a
  // missed job:completed event would otherwise strand forever.
  const jobStatus = useLatestJobLive(projectId).data?.status;
  useEffect(() => {
    if (jobStatus && jobStatus !== "RUNNING" && jobStatus !== "PENDING") {
      clearFinishedStage("generate");
    }
  }, [jobStatus]);
  const running = useLiveRunStore((s) => s.running);
  return useMemo(() => Object.values(running), [running]);
}
