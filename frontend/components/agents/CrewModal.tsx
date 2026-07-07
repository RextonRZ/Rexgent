"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Check,
  Clapperboard,
  Film,
  Link2,
  Loader2,
  PenLine,
  Scissors,
  Users,
  Volume2,
  Wallet,
  X,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useLedger } from "@/hooks/useLedger";
import { useProjectProgress } from "@/hooks/useProjectProgress";
import { useReducedMotion } from "@/hooks/useReducedMotion";
import {
  STAGE_LABELS,
  STAGE_ORDER,
  ensureLiveRun,
  mapActiveByStage,
  useLiveRunStore,
  useRunningStages,
  type StageKey,
  type TrailEntry,
} from "@/hooks/useLiveRun";

const STAGE_ICONS: Record<StageKey, LucideIcon> = {
  script: PenLine,
  characters: Users,
  storyboard: Clapperboard,
  generate: Film,
  export: Scissors,
};

/** Same crew metaphor as Studio stats — one naming scheme everywhere. */
const AGENT_ICONS: Record<string, LucideIcon> = {
  Screenwriter: PenLine,
  "Casting Director": Users,
  Casting: Users,
  Director: Clapperboard,
  "Story Analyst": Link2,
  Renderer: Film,
  Continuity: Link2,
  Producer: Wallet,
  "Audio Mixer": Volume2,
  Editor: Scissors,
  Showrunner: Clapperboard,
};

/** Ledger by_stage keys attributed to each pipeline stage (shown only if > 0). */
const STAGE_COST_KEYS: Record<StageKey, string[]> = {
  script: ["script", "structure", "judge", "revise", "title", "plot_gap", "ending"],
  characters: ["characters", "relationships", "mbti", "appearance", "clarify"],
  storyboard: ["storyboard", "set_dress", "prompt_craft", "style"],
  generate: ["generation", "casting", "audio", "budget", "wardrobe", "regen_rewrite"],
  export: ["export"],
};

type StageStatus = "done" | "active" | "failed" | "pending";

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${Math.round(n / 1_000)}K`;
  return String(n);
}

const fmtTime = (at: number) =>
  new Date(at).toLocaleTimeString("en-GB", { hour12: false });

function TrailIcon({ kind }: { kind: TrailEntry["kind"] }) {
  if (kind === "done") return <Check className="mt-0.5 size-3 shrink-0 text-ok" />;
  if (kind === "warn")
    return <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />;
  if (kind === "fail") return <X className="mt-0.5 size-3 shrink-0 text-bad" />;
  return <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-600" />;
}

/** Compact crew view for the dock column — same store, same stages, at a
 * glance. The full node-graph modal opens from its footer button. */
export function CrewDockPanel({
  projectId,
  onOpenFull,
}: {
  projectId: string;
  onOpenFull: () => void;
}) {
  const reduced = useReducedMotion();
  const progress = useProjectProgress(projectId);
  const running = useRunningStages(projectId);
  const failed = useLiveRunStore((s) => s.failed);
  const activeByStage = useMemo(() => mapActiveByStage(running), [running]);

  const activeKeys = STAGE_ORDER.filter((k) => activeByStage[k]);
  const doneCount = progress
    ? STAGE_ORDER.filter((k) => progress[k]).length
    : 0;

  return (
    <div className="flex flex-col gap-1">
      <p className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">
        <span className="relative flex h-2 w-2 shrink-0">
          {activeKeys.length ? (
            <>
              <span className="absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-60 motion-safe:animate-ping" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-violet-400" />
            </>
          ) : (
            <span className="inline-flex h-2 w-2 rounded-full bg-zinc-600" />
          )}
        </span>
        {activeKeys.length
          ? `Crew working · ${activeKeys.map((k) => STAGE_LABELS[k]).join(" + ")}`
          : `Crew idle · ${doneCount}/${STAGE_ORDER.length} done`}
      </p>

      {STAGE_ORDER.map((key) => {
        const live = activeByStage[key];
        const st: StageStatus = live
          ? "active"
          : failed[key]
            ? "failed"
            : progress?.[key]
              ? "done"
              : "pending";
        const Icon = STAGE_ICONS[key];
        return (
          <div key={key} className="flex items-center gap-2.5 px-1 py-1">
            <span
              className={cn(
                "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border",
                st === "active" &&
                  "border-violet-400/60 bg-violet-500/15 text-violet-200",
                st === "done" && "border-ok/40 bg-ok/10 text-ok",
                st === "failed" &&
                  "border-amber-400/50 bg-amber-500/10 text-amber-300",
                st === "pending" && "border-white/10 bg-zinc-900 text-zinc-600"
              )}
            >
              {st === "done" ? (
                <Check className="size-3" />
              ) : (
                <Icon className="size-3" />
              )}
            </span>
            <div className="min-w-0 flex-1">
              <p
                className={cn(
                  "text-xs font-medium",
                  st === "active"
                    ? "text-violet-200"
                    : st === "done"
                      ? "text-zinc-300"
                      : st === "failed"
                        ? "text-amber-300"
                        : "text-zinc-600"
                )}
              >
                {STAGE_LABELS[key]}
              </p>
              {live && (
                <p className="truncate text-[10px] text-muted-foreground">
                  {live.agent}: {live.label}
                  {live.index && live.total ? ` · ${live.index}/${live.total}` : ""}
                </p>
              )}
              {!live && failed[key] && (
                <p className="truncate text-[10px] text-amber-300/80">
                  {failed[key]}
                </p>
              )}
            </div>
            {st === "active" &&
              (reduced ? (
                <span className="h-2 w-2 shrink-0 rounded-full bg-violet-400" />
              ) : (
                <Loader2 className="size-3.5 shrink-0 animate-spin text-violet-300" />
              ))}
          </div>
        );
      })}

      <button
        onClick={onOpenFull}
        className="mt-2 w-full rounded-lg border hairline py-1.5 text-xs text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
      >
        Open full pipeline →
      </button>
    </div>
  );
}

/** Deliberately NON-modal: the overlay stops at `insetRight`, so the dock's
 * Showrunner chat and Live cost stay visible and clickable beside the full
 * pipeline — three synchronized views of the same run. ESC or the dimmed
 * backdrop closes it. */
export function CrewModal({
  projectId,
  open,
  onOpenChange,
  insetRight = 0,
}: {
  projectId: string;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  /** px kept clear on the right so the dock stays usable */
  insetRight?: number;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-y-0 left-0 z-40"
      style={{ right: insetRight }}
    >
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm duration-200 animate-in fade-in-0"
        onClick={() => onOpenChange(false)}
      />
      <div
        role="dialog"
        aria-label="Your crew"
        className="absolute left-1/2 top-1/2 flex max-h-[85vh] w-[min(92%,880px)] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#0b0912] shadow-2xl duration-200 animate-in fade-in-0 zoom-in-95"
      >
        <CrewModalBody
          projectId={projectId}
          onClose={() => onOpenChange(false)}
        />
      </div>
    </div>
  );
}

function CrewModalBody({
  projectId,
  onClose,
}: {
  projectId: string;
  onClose: () => void;
}) {
  const reduced = useReducedMotion();
  const progress = useProjectProgress(projectId);
  const ledger = useLedger(projectId);
  const running = useRunningStages(projectId);
  const trail = useLiveRunStore((s) => s.trail);
  const failed = useLiveRunStore((s) => s.failed);
  const [openPanels, setOpenPanels] = useState<StageKey[]>([]);

  useEffect(() => {
    ensureLiveRun(projectId);
  }, [projectId]);

  const activeByStage = useMemo(() => mapActiveByStage(running), [running]);

  const statusOf = (key: StageKey): StageStatus => {
    if (activeByStage[key]) return "active";
    if (failed[key]) return "failed";
    if (progress?.[key]) return "done";
    return "pending";
  };

  // a stage error auto-surfaces its detail panel
  useEffect(() => {
    const bad = STAGE_ORDER.filter((k) => failed[k]);
    if (!bad.length) return;
    setOpenPanels((cur) => [...cur, ...bad.filter((k) => !cur.includes(k))]);
  }, [failed]);

  const togglePanel = (key: StageKey) =>
    setOpenPanels((cur) =>
      cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key]
    );

  const activeKeys = STAGE_ORDER.filter((k) => activeByStage[k]);
  const doneCount = progress
    ? STAGE_ORDER.filter((k) => progress[k]).length
    : 0;
  const grand = ledger?.grand_total ?? 0;
  const tokens = ledger?.llm?.total_tokens ?? 0;

  const statusLine = activeKeys.length
    ? `Working on ${activeKeys.map((k) => STAGE_LABELS[k]).join(" + ")} · $${grand.toFixed(2)} spent`
    : doneCount === STAGE_ORDER.length
      ? `All caught up · $${grand.toFixed(2)} spent`
      : `Crew idle · ${doneCount}/${STAGE_ORDER.length} stages done · $${grand.toFixed(2)} spent`;

  // tool nodes branch under the FIRST active stage: latest entry per agent
  const activeKey = activeKeys[0];
  const tools = useMemo(() => {
    if (!activeKey) return [];
    const latest = new Map<string, TrailEntry>();
    for (const e of trail[activeKey]) latest.set(e.agent, e);
    return Array.from(latest.values()).slice(-5);
  }, [trail, activeKey]);
  const runningAgent = activeKey ? activeByStage[activeKey]?.agent : undefined;
  const activeIdx = activeKey ? STAGE_ORDER.indexOf(activeKey) : -1;
  // node centers sit at 10%, 30%, 50%, 70%, 90% of the rail
  const centerPct = activeIdx >= 0 ? activeIdx * 20 + 10 : 0;

  const sessionQuiet =
    activeKeys.length === 0 &&
    STAGE_ORDER.every((k) => trail[k].length === 0);

  return (
    <>
      {/* header — cost and tokens reuse the same query the dock reads */}
      <div className="flex items-start justify-between gap-4 border-b border-white/[0.08] px-6 py-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Your crew</h2>
          <p className="mt-0.5 text-xs text-zinc-500">{statusLine}</p>
        </div>
        <div className="flex items-center gap-3">
          {tokens > 0 && (
            <span className="hidden text-[11px] tabular-nums text-zinc-500 sm:block">
              {fmtTokens(tokens)} tokens
            </span>
          )}
          <button
            onClick={onClose}
            aria-label="Close crew view"
            className="rounded-md p-1 text-zinc-400 transition-all duration-150 hover:bg-white/10 hover:text-white motion-safe:hover:rotate-90 motion-reduce:transition-none"
          >
            <X className="size-5" />
          </button>
        </div>
      </div>

      {/* stage changes are announced for screen readers */}
      <p aria-live="polite" role="status" className="sr-only">
        {activeKeys.length
          ? `Crew working on ${activeKeys.map((k) => STAGE_LABELS[k]).join(" and ")}`
          : "Crew idle"}
      </p>

      <div className="scroll-clean min-h-0 flex-1 space-y-5 overflow-y-auto p-6">
        {/* ── the pipeline rail ── */}
        <div className="relative">
          {/* connectors behind the nodes: solid when crossed, dashed ahead */}
          <div aria-hidden className="absolute inset-x-0 top-[22px]">
            {STAGE_ORDER.slice(0, -1).map((key, i) => {
              const crossed = progress?.[key];
              const intoActive = statusOf(STAGE_ORDER[i + 1]) === "active";
              return (
                <span
                  key={key}
                  className={cn(
                    "absolute top-0",
                    crossed
                      ? intoActive
                        ? "h-px bg-gradient-to-r from-ok/40 to-violet-400/60"
                        : "h-px bg-ok/40"
                      : "h-0 border-t border-dashed border-white/15"
                  )}
                  style={{ left: `${i * 20 + 10}%`, width: "20%" }}
                />
              );
            })}
          </div>

          <div className="relative grid grid-cols-5">
            {STAGE_ORDER.map((key) => {
              const st = statusOf(key);
              const Icon = STAGE_ICONS[key];
              const live = activeByStage[key];
              const isOpen = openPanels.includes(key);
              return (
                <div key={key} className="flex flex-col items-center gap-1.5">
                  <button
                    onClick={() => togglePanel(key)}
                    aria-expanded={isOpen}
                    aria-label={`${STAGE_LABELS[key]} details`}
                    className={cn(
                      "relative flex h-11 w-11 items-center justify-center rounded-full border transition-colors duration-150 motion-reduce:transition-none",
                      st === "active" &&
                        "border-violet-400/60 bg-violet-500/15 text-violet-200 ring-2 ring-violet-400/30",
                      st === "done" && "border-ok/40 bg-ok/10 text-ok",
                      st === "failed" &&
                        "border-amber-400/50 bg-amber-500/10 text-amber-300",
                      st === "pending" &&
                        "border-white/10 bg-zinc-900 text-zinc-600",
                      "hover:border-white/30"
                    )}
                  >
                    <Icon className="size-4" />
                    {st === "active" && !reduced && (
                      <span
                        aria-hidden
                        className="absolute -inset-1 rounded-full border-2 border-transparent border-t-violet-400/70 motion-safe:animate-spin"
                      />
                    )}
                    {st === "done" && (
                      <span className="absolute -bottom-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-ok text-black">
                        <Check className="size-2.5" strokeWidth={3} />
                      </span>
                    )}
                  </button>
                  <span
                    className={cn(
                      "text-[11px] font-medium",
                      st === "active"
                        ? "text-violet-200"
                        : st === "done"
                          ? "text-zinc-300"
                          : st === "failed"
                            ? "text-amber-300"
                            : "text-zinc-600"
                    )}
                  >
                    {STAGE_LABELS[key]}
                  </span>
                  <span className="h-3.5 max-w-full truncate px-1 text-[10px] tabular-nums text-zinc-500">
                    {live
                      ? live.index && live.total
                        ? `${live.index}/${live.total}`
                        : "working"
                      : failed[key]
                        ? "needs a look"
                        : ""}
                  </span>
                </div>
              );
            })}
          </div>

          {/* ── tool branch under the active stage ── */}
          {activeKey && tools.length > 0 && (
            <div className="relative mt-1 h-[74px]">
              <svg
                aria-hidden
                className="absolute top-0 h-4 w-px overflow-visible"
                style={{ left: `${centerPct}%` }}
              >
                <line
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="16"
                  stroke="rgb(167 139 250 / 0.5)"
                  strokeWidth="2"
                  strokeDasharray="3 3"
                  className={reduced ? undefined : "dash-flow"}
                />
              </svg>
              <div
                className="absolute top-4 flex max-w-full -translate-x-1/2 flex-wrap justify-center gap-1.5"
                style={{
                  left: `clamp(120px, ${centerPct}%, calc(100% - 120px))`,
                }}
              >
                {tools.map((t) => {
                  const ToolIcon = AGENT_ICONS[t.agent] ?? Clapperboard;
                  const isRunning = t.agent === runningAgent;
                  return (
                    <span
                      key={t.agent}
                      title={t.label}
                      className={cn(
                        "flex items-center gap-1.5 rounded-full border px-2 py-1 font-mono text-[10px] transition-colors duration-150 motion-reduce:transition-none",
                        isRunning
                          ? "border-violet-400/50 bg-violet-500/10 text-violet-200"
                          : t.kind === "fail"
                            ? "border-bad/30 text-bad"
                            : t.kind === "warn"
                              ? "border-amber-400/30 text-amber-300"
                              : t.kind === "done"
                                ? "border-white/10 text-zinc-300"
                                : "border-white/[0.06] text-zinc-600"
                      )}
                    >
                      {isRunning ? (
                        reduced ? (
                          <span className="h-2 w-2 rounded-full bg-violet-400" />
                        ) : (
                          <Loader2 className="size-3 animate-spin" />
                        )
                      ) : (
                        <ToolIcon className="size-3" />
                      )}
                      {t.agent}
                      {!isRunning && t.kind === "done" && (
                        <Check className="size-2.5 text-ok" />
                      )}
                    </span>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {sessionQuiet && (
          <p className="text-center text-xs text-zinc-500">
            {doneCount > 0
              ? "Nothing running right now. Click a stage to review what exists."
              : "Your crew reports for duty when you start a stage."}
          </p>
        )}

        {/* ── expanded process panels: open several, close them one by one ── */}
        {openPanels.map((key) => {
          const Icon = STAGE_ICONS[key];
          const st = statusOf(key);
          const entries = trail[key];
          const cost = STAGE_COST_KEYS[key].reduce(
            (sum, k) => sum + (ledger?.by_stage?.[k] ?? 0),
            0
          );
          return (
            <div
              key={key}
              className="rounded-xl border border-white/10 bg-white/[0.02]"
            >
              <div className="flex items-center gap-2 border-b border-white/[0.06] px-3 py-2">
                <Icon className="size-4 text-zinc-400" />
                <span className="text-sm font-medium">{STAGE_LABELS[key]}</span>
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-[10px] font-medium",
                    st === "active" && "bg-violet-500/15 text-violet-300",
                    st === "done" && "bg-ok/10 text-ok",
                    st === "failed" && "bg-amber-500/15 text-amber-300",
                    st === "pending" && "bg-white/5 text-zinc-500"
                  )}
                >
                  {st === "active"
                    ? "working"
                    : st === "done"
                      ? "done"
                      : st === "failed"
                        ? "needs a look"
                        : "not started"}
                </span>
                {cost > 0 && (
                  <span className="text-[11px] tabular-nums text-zinc-500">
                    ${cost.toFixed(2)}
                  </span>
                )}
                <button
                  onClick={() => togglePanel(key)}
                  aria-label={`Close ${STAGE_LABELS[key]} details`}
                  className="ml-auto rounded-md p-1 text-zinc-500 transition-colors duration-150 hover:bg-white/10 hover:text-white motion-reduce:transition-none"
                >
                  <X className="size-3.5" />
                </button>
              </div>
              <div className="scroll-clean max-h-44 overflow-y-auto px-3 py-2">
                {entries.length === 0 ? (
                  <p className="py-1 text-xs text-zinc-500">
                    {progress?.[key]
                      ? "Finished before this session — open the page to see its artifacts."
                      : "No activity yet this session."}
                  </p>
                ) : (
                  entries.map((e, i) => (
                    <div
                      key={`${e.at}-${i}`}
                      className="flex items-start gap-2 py-0.5 text-xs"
                    >
                      <span className="w-14 shrink-0 font-mono text-[10px] leading-4 text-zinc-600">
                        {fmtTime(e.at)}
                      </span>
                      <TrailIcon kind={e.kind} />
                      <span className="min-w-0 text-zinc-400">
                        <span className="font-medium text-zinc-300">
                          {e.agent}
                        </span>{" "}
                        {e.label}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}
