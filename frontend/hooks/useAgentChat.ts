import { useEffect, useMemo, useRef, useState } from "react";
import { getSocket } from "@/lib/websocket";
import { useAgentReports } from "./useAgents";
import { useActivityFeed, type FeedItem } from "./useActivityFeed";
import {
  ensureLiveRun,
  subscribeFinished,
  useRunningStages,
  NODE_LABELS,
} from "./useLiveRun";

// Live run state lives in ONE shared store (useLiveRun) so the chat, the
// dock's crew status and the crew modal can never disagree.
export type { StageProgress, RunningStage } from "./useLiveRun";

export interface ChatMessage {
  id: string;
  at: number;
  agent: string;
  kind: "done" | "info" | "warn" | "fail";
  text: string;
  detail?: string;
  pct?: number;
  /** how many identical lines collapsed into this one (>=2 shows a badge) */
  _count?: number;
}

let _mid = 0;
const nextId = () => `m${++_mid}`;

/** Server timestamps are naive UTC (datetime.utcnow); without a zone marker the
 * browser reads them as LOCAL time, shifting them by the tz offset so a fresh
 * answer sorts BEFORE the message that prompted it. Anchor them to UTC. */
function parseServerTime(s?: string): number {
  if (!s) return Date.now();
  const hasZone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(s);
  const t = Date.parse(hasZone ? s : `${s}Z`);
  return Number.isNaN(t) ? Date.now() : t;
}

/** Live "who is working right now", read from the shared live-run store.
 * Completed/failed stages hand a message to the caller (chat bubbles). */
export function useStageProgress(
  projectId: string,
  onFinished?: (msg: ChatMessage) => void
) {
  const cb = useRef(onFinished);
  cb.current = onFinished;

  useEffect(() => {
    ensureLiveRun(projectId);
    return subscribeFinished((m) =>
      cb.current?.({
        id: nextId(),
        at: Date.now(),
        agent: m.agent,
        kind: m.failed ? "fail" : "done",
        text: m.label,
      })
    );
  }, [projectId]);

  return useRunningStages(projectId);
}

/** Friendly copy for raw activity events; null = not worth a chat line. */
function feedToMessage(item: FeedItem): ChatMessage | null {
  const p = item.payload ?? {};
  const base = { id: nextId(), at: item.at };
  switch (item.event) {
    case "casting.started":
      return { ...base, agent: "Casting Director", kind: "info", text: "Casting the production bible" };
    case "casting.wardrobe_plan.completed":
      return { ...base, agent: "Casting Director", kind: "done", text: `Wardrobe planned: ${p.variant_count ?? "?"} outfit(s)` };
    case "casting.plate.completed": {
      // keys are slugs ("IM SOL:fan outfit", "ryu_sun_jae_s_dressing_room") —
      // say them like a person would
      const kind = String(p.kind ?? "plate");
      const rawKey = String(p.key ?? "");
      let what: string;
      if (kind === "style") {
        what = "the visual style frame";
      } else if (kind === "character") {
        const [who, outfit] = rawKey.split(":");
        what = outfit ? `${who} (${outfit})` : who;
      } else {
        what = `${kind} ${rawKey.replace(/_/g, " ").replace(/ s /g, "'s ")}`;
      }
      // location/style plates paint at storyboard time — that's the Director's work
      const speaker = kind === "location" || kind === "style" ? "Director" : "Casting Director";
      return { ...base, agent: speaker, kind: "done", text: `Plate ready: ${what}`, detail: p.total ? `${p.index}/${p.total}` : undefined };
    }
    case "casting.completed":
      // awaiting-review already speaks twice (the stage line and the review
      // card) — only the auto-approved outcome needs its own line
      return p.auto_approved
        ? { ...base, agent: "Casting Director", kind: "done", text: "Bible cast and auto approved" }
        : null;
    case "generation.shot.completed":
      return { ...base, agent: "Renderer", kind: p.status === "APPROVED" ? "done" : "warn", text: `Scene ${p.scene_number} shot ${p.shot_number} rendered${p.status === "APPROVED" ? "" : ", flagged for review"}` };
    case "continuity.flagged":
      return { ...base, agent: "Continuity", kind: "warn", text: `Continuity flagged a clip at ${p.continuity_score}%` };
    case "job:completed":
      return { ...base, agent: "Renderer", kind: "done", text: `All clips rendered: ${p.total_clips} clip(s) for $${p.total_cost}` };
    case "job:budget_exhausted":
      return { ...base, agent: "Producer", kind: "warn", text: "Stopped at the spend cap, review what rendered" };
    case "job:blocked":
      return { ...base, agent: "Producer", kind: "fail", text: `Generation blocked: ${(p.issues ?? []).join("; ") || "pre-flight failed"}` };
    default:
      return null;
  }
}

/** The showrunner conversation: persistent agent reports + live activity +
 * stage progress merged into one chronological feed, plus who's typing. */
export function useAgentChat(projectId: string) {
  const reports = useAgentReports(projectId);
  const feed = useActivityFeed(projectId);
  const [ephemeral, setEphemeral] = useState<ChatMessage[]>([]);
  const running = useStageProgress(projectId, (msg) =>
    setEphemeral((cur) => [...cur.slice(-40), msg])
  );

  // e.g. the user's own chat question, shown immediately
  const pushLocal = (m: Omit<ChatMessage, "id" | "at">) =>
    setEphemeral((cur) => [
      ...cur.slice(-40),
      { ...m, id: nextId(), at: Date.now() },
    ]);

  // Auto-run trace: node hops read as terse "moving on" lines.
  useEffect(() => {
    const socket = getSocket();
    socket.connect();
    socket.emit("join_project", { project_id: projectId });
    const handler = (d: { node: string }) => {
      const label = NODE_LABELS[d.node];
      if (!label) return;
      setEphemeral((cur) => [
        ...cur.slice(-40),
        { id: nextId(), at: Date.now(), agent: "Showrunner", kind: "info", text: label },
      ]);
    };
    socket.on("agent:node", handler);
    return () => {
      socket.off("agent:node", handler);
    };
  }, [projectId]);

  const messages = useMemo(() => {
    const out: ChatMessage[] = [];
    for (const r of reports) {
      const passed = /pass/i.test(r.rationale ?? "") || (r.confidence ?? 0) >= 0.7;
      out.push({
        id: `r-${r.created_at ?? ""}-${r.agent}-${out.length}`,
        at: parseServerTime(r.created_at),
        agent: r.agent,
        kind: passed ? "done" : "warn",
        text: r.rationale || r.stage,
        pct: Math.round(Math.min(Math.max(r.confidence ?? 0, 0), 1) * 100),
      });
    }
    for (const item of feed) {
      const m = feedToMessage(item);
      if (m) out.push(m);
    }
    out.push(...ephemeral);
    out.sort((a, b) => a.at - b.at);

    // Collapse a run of identical done-lines (e.g. "Continuity passed" x4) into
    // one bubble with a count, so the feed reads like a process log not a wall.
    const merged: ChatMessage[] = [];
    for (const m of out) {
      const last = merged[merged.length - 1];
      if (last && last.agent === m.agent && last.kind === m.kind && last.text === m.text) {
        const n = (last._count ?? 1) + 1;
        merged[merged.length - 1] = { ...last, _count: n, pct: m.pct, at: m.at };
      } else {
        merged.push(m);
      }
    }
    return merged.slice(-60);
  }, [reports, feed, ephemeral]);

  return { messages, running, pushLocal };
}
