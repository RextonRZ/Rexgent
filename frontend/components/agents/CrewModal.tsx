"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Check,
  ChevronDown,
  Clapperboard,
  Film,
  Loader2,
  PenLine,
  Scissors,
  Users,
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
  type ToolState,
  type TrailEntry,
} from "@/hooks/useLiveRun";
import {
  FALLBACK_TOOL_ICON,
  STAGE_AGENT,
  STAGE_AGENT_ICONS,
  STAGE_TOOLS,
  TOOL_KIND_COPY,
  TOOL_RUN_HINT,
  type ToolSpec,
} from "@/lib/stageTools";

const STAGE_ICONS: Record<StageKey, LucideIcon> = {
  script: PenLine,
  characters: Users,
  storyboard: Clapperboard,
  generate: Film,
  export: Scissors,
};

/** Ledger by_stage keys attributed to each pipeline stage (shown only if > 0). */
const STAGE_COST_KEYS: Record<StageKey, string[]> = {
  script: ["script", "structure", "judge", "revise", "title", "plot_gap", "ending"],
  characters: ["characters", "relationships", "mbti", "appearance", "clarify", "casting", "wardrobe"],
  storyboard: ["storyboard", "set_dress", "prompt_craft", "style"],
  generate: ["generation", "audio", "budget", "regen_rewrite"],
  export: ["export"],
};

type StageStatus = "done" | "active" | "failed" | "pending";
type ToolNodeStatus = "idle" | "run" | "done" | "fail";

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

/** The stage's tool nodes in render order: the fixed topology first, then any
 * tool the backend emitted that we didn't predeclare (never hide machinery). */
function orderedTools(
  stage: StageKey,
  live: Record<string, ToolState>
): { spec: ToolSpec; state?: ToolState }[] {
  const fixed = STAGE_TOOLS[stage].map((spec) => ({ spec, state: live[spec.key] }));
  const known = new Set(STAGE_TOOLS[stage].map((t) => t.key));
  const extras = Object.values(live)
    .filter((t) => !known.has(t.tool))
    .sort((a, b) => a.at - b.at)
    .map((state) => ({
      spec: { key: state.tool, icon: FALLBACK_TOOL_ICON, kind: "service" as const },
      state,
    }));
  return [...fixed, ...extras];
}

const toolStatus = (state?: ToolState): ToolNodeStatus => state?.status ?? "idle";

/** One tool node card: idle faint → spinning+glow → green tick / amber retry. */
function ToolNode({
  spec,
  state,
  reduced,
}: {
  spec: ToolSpec;
  state?: ToolState;
  reduced: boolean;
}) {
  const st = toolStatus(state);
  const Icon = spec.icon;
  const retry =
    st === "fail" && state?.index && state?.total
      ? `retry ${state.index}/${state.total}`
      : null;
  // a node that won't fire by itself says so while idle, instead of looking
  // like a step the crew forgot
  const idleHint = st === "idle" && spec.run ? TOOL_RUN_HINT[spec.run] : null;
  return (
    <div
      title={`${spec.key} · ${TOOL_KIND_COPY[spec.kind]}${
        state?.agent ? ` · ${state.agent}` : ""
      }${spec.trigger ? ` · ${spec.trigger}` : ""}${
        state?.error ? ` · ${state.error}` : ""
      }`}
      className={cn(
        "relative flex w-full flex-col items-center gap-0.5 rounded-lg border px-1 py-1.5 transition-colors duration-150 motion-reduce:transition-none",
        st === "idle" &&
          (spec.run
            ? "border-dashed border-white/[0.08] text-zinc-600"
            : "border-white/[0.06] text-zinc-600"),
        st === "run" &&
          "border-violet-400/50 bg-violet-500/10 text-violet-200 ring-2 ring-violet-400/20",
        st === "done" && "border-ok/30 bg-ok/[0.04] text-zinc-300",
        st === "fail" && "border-amber-400/50 bg-amber-500/10 text-amber-300"
      )}
    >
      {st === "run" ? (
        reduced ? (
          <span className="my-0.5 h-2.5 w-2.5 rounded-full bg-violet-400" />
        ) : (
          <Loader2 className="size-3.5 animate-spin" />
        )
      ) : (
        <Icon className="size-3.5" />
      )}
      <span className="max-w-full truncate font-mono text-[9px] leading-3">
        {spec.key}
      </span>
      <span
        className={cn(
          "h-3 max-w-full truncate text-[9px] leading-3",
          idleHint ? "italic text-zinc-600" : "text-zinc-500"
        )}
      >
        {st === "run" && state?.index && state?.total
          ? `${state.index}/${state.total}`
          : retry ?? (st === "fail" ? "failed" : idleHint ?? "")}
      </span>
      {st === "done" && (
        <span className="absolute -right-1 -top-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-ok text-black">
          <Check className="size-2" strokeWidth={3} />
        </span>
      )}
    </div>
  );
}

/** The level-2 sub-graph: the stage's agent hub branching down to its tool
 * nodes, artifact labels riding the edges. Pure SVG+CSS on a fixed topology. */
function StageToolGraph({
  stage,
  live,
  reduced,
}: {
  stage: StageKey;
  live: Record<string, ToolState>;
  reduced: boolean;
}) {
  const nodes = orderedTools(stage, live);
  const n = nodes.length;
  const AgentIcon = STAGE_AGENT_ICONS[stage];
  const anyRun = nodes.some((t) => toolStatus(t.state) === "run");

  const edgeClass = (st: ToolNodeStatus) =>
    st === "run"
      ? "stroke-violet-400/70"
      : st === "done"
        ? "stroke-ok/40"
        : st === "fail"
          ? "stroke-amber-400/60"
          : "stroke-white/10";

  return (
    <>
      {/* ── wide: hub above, tools fan out below (scrolls sideways if tight) ── */}
      <div className="scroll-clean hidden overflow-x-auto sm:block">
        <div style={{ minWidth: `${n * 84}px` }}>
          <div className="relative z-10 flex justify-center">
            <span
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px]",
                anyRun
                  ? "border-violet-400/50 bg-violet-500/10 text-violet-200"
                  : "border-white/10 bg-zinc-900 text-zinc-400"
              )}
            >
              <AgentIcon className="size-3" />
              {STAGE_AGENT[stage]}
            </span>
          </div>
          <svg
            aria-hidden
            className="block h-8 w-full"
            viewBox="0 0 100 32"
            preserveAspectRatio="none"
          >
            {nodes.map((t, i) => {
              const st = toolStatus(t.state);
              const x = ((i + 0.5) / n) * 100;
              return (
                <path
                  key={t.spec.key}
                  d={`M 50 0 C 50 16, ${x} 10, ${x} 32`}
                  fill="none"
                  vectorEffect="non-scaling-stroke"
                  strokeWidth="1.5"
                  strokeDasharray={st === "done" || st === "fail" ? undefined : "3 3"}
                  className={cn(
                    edgeClass(st),
                    st === "run" && !reduced && "dash-flow"
                  )}
                />
              );
            })}
          </svg>
          {/* artifact labels sit ON the edges, right where they land */}
          <div
            className="grid gap-1.5"
            style={{ gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))` }}
          >
            {nodes.map((t) => (
              <div key={t.spec.key} className="flex flex-col items-center">
                <span
                  className={cn(
                    "relative z-10 -mt-3 mb-0.5 h-4 max-w-full truncate rounded bg-[#0b0912] px-1 text-[9px] leading-4",
                    t.state?.artifact ? "text-zinc-400" : "text-transparent"
                  )}
                >
                  {t.state?.artifact ?? "·"}
                </span>
                <ToolNode spec={t.spec} state={t.state} reduced={reduced} />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── narrow: the same graph stacked vertically ── */}
      <div className="sm:hidden">
        <span className="flex w-fit items-center gap-1.5 rounded-full border border-white/10 bg-zinc-900 px-3 py-1 text-[11px] text-zinc-400">
          <AgentIcon className="size-3" />
          {STAGE_AGENT[stage]}
        </span>
        <div className="ml-3 border-l border-white/10 pl-3 pt-1.5">
          {nodes.map((t) => {
            const st = toolStatus(t.state);
            const Icon = t.spec.icon;
            const idleHint =
              st === "idle" && t.spec.run ? TOOL_RUN_HINT[t.spec.run] : null;
            return (
              <div
                key={t.spec.key}
                title={t.spec.trigger}
                className="flex items-center gap-2 py-1"
              >
                {st === "run" ? (
                  reduced ? (
                    <span className="h-2 w-2 shrink-0 rounded-full bg-violet-400" />
                  ) : (
                    <Loader2 className="size-3 shrink-0 animate-spin text-violet-300" />
                  )
                ) : st === "done" ? (
                  <Check className="size-3 shrink-0 text-ok" />
                ) : st === "fail" ? (
                  <X className="size-3 shrink-0 text-amber-300" />
                ) : (
                  <Icon className="size-3 shrink-0 text-zinc-600" />
                )}
                <span
                  className={cn(
                    "font-mono text-[10px]",
                    st === "run"
                      ? "text-violet-200"
                      : st === "done"
                        ? "text-zinc-300"
                        : st === "fail"
                          ? "text-amber-300"
                          : "text-zinc-600"
                  )}
                >
                  {t.spec.key}
                </span>
                {t.state?.artifact ? (
                  <span className="truncate text-[9px] text-zinc-500">
                    {t.state.artifact}
                  </span>
                ) : idleHint ? (
                  <span className="truncate text-[9px] italic text-zinc-600">
                    {idleHint}
                  </span>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}

/** Compact crew view for the dock column — same store, same stages, same tool
 * states at a glance. The full node-graph modal opens from its footer button. */
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
  const tools = useLiveRunStore((s) => s.tools);
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
        const stageTools = tools[key];
        const hasToolState = Object.keys(stageTools).length > 0;
        return (
          <div key={key} className="px-1 py-1">
            <div className="flex items-center gap-2.5">
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
            {/* per-tool ticks — identical data to the modal's sub-graph */}
            {hasToolState && (
              <div className="ml-[34px] mt-1 flex flex-wrap gap-1">
                {orderedTools(key, stageTools).map((t) => {
                  const ts = toolStatus(t.state);
                  if (ts === "idle") return null;
                  return (
                    <span
                      key={t.spec.key}
                      title={`${t.spec.key}${t.state?.artifact ? ` · ${t.state.artifact}` : ""}`}
                      className={cn(
                        "h-1.5 w-1.5 rounded-full",
                        ts === "run" &&
                          "bg-violet-400 motion-safe:animate-pulse",
                        ts === "done" && "bg-ok/70",
                        ts === "fail" && "bg-amber-400"
                      )}
                    />
                  );
                })}
              </div>
            )}
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

/** Deliberately NON-modal in layout: the overlay stops at `insetRight`, so the
 * dock's Showrunner chat and Live cost stay visible beside the full pipeline —
 * three synchronized views of the same run. Keyboard focus IS trapped inside
 * (and restored on close); ESC or the dimmed backdrop closes it. */
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
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const restoreTo = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onOpenChange(false);
        return;
      }
      if (e.key !== "Tab" || !panelRef.current) return;
      const focusables = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
      ).filter((el) => !el.hasAttribute("disabled"));
      if (!focusables.length) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const current = document.activeElement;
      if (e.shiftKey && (current === first || current === panelRef.current)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && current === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      restoreTo?.focus?.();
    };
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
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Your crew"
        tabIndex={-1}
        className="absolute left-1/2 top-1/2 flex max-h-[85vh] w-[min(92%,880px)] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#0b0912] shadow-2xl outline-none duration-200 animate-in fade-in-0 zoom-in-95"
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
  const tools = useLiveRunStore((s) => s.tools);
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

  // the ACTIVE stage auto-expands its sub-graph; failures auto-surface too
  useEffect(() => {
    const want = STAGE_ORDER.filter((k) => failed[k] || activeByStage[k]);
    if (!want.length) return;
    setOpenPanels((cur) => [...cur, ...want.filter((k) => !cur.includes(k))]);
  }, [failed, activeByStage]);

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
    ? `Working on ${activeKeys.map((k) => STAGE_LABELS[k]).join(" + ")}`
    : doneCount === STAGE_ORDER.length
      ? "All caught up"
      : `Crew idle · ${doneCount}/${STAGE_ORDER.length} stages done`;

  // screen-reader narration of tool transitions ("dispatch_video complete,
  // verify_face running") — announced only when a status actually changes
  const [announcement, setAnnouncement] = useState("");
  const lastStatuses = useRef<Map<string, string>>(new Map());
  useEffect(() => {
    const parts: string[] = [];
    for (const stage of STAGE_ORDER) {
      for (const t of Object.values(tools[stage])) {
        const id = `${stage}:${t.tool}`;
        const prev = lastStatuses.current.get(id);
        if (prev === t.status) continue;
        lastStatuses.current.set(id, t.status);
        if (t.status === "done") parts.push(`${t.tool} complete`);
        else if (t.status === "fail") parts.push(`${t.tool} failed`);
        else if (t.status === "run" && prev === undefined)
          parts.push(`${t.tool} running`);
      }
    }
    if (parts.length) setAnnouncement(parts.slice(-2).join(", "));
  }, [tools]);

  const stageCost = (key: StageKey) =>
    STAGE_COST_KEYS[key].reduce((sum, k) => sum + (ledger?.by_stage?.[k] ?? 0), 0);

  const sessionQuiet =
    activeKeys.length === 0 &&
    STAGE_ORDER.every(
      (k) => trail[k].length === 0 && Object.keys(tools[k]).length === 0
    );

  return (
    <>
      {/* header — live cost + token ticker reuse the same query the dock reads */}
      <div className="flex items-start justify-between gap-4 border-b border-white/[0.08] px-6 py-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Your crew</h2>
          <p className="mt-0.5 text-xs text-zinc-500">{statusLine}</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[11px] tabular-nums text-zinc-400">
            ${grand.toFixed(2)}
            {tokens > 0 && (
              <span className="hidden text-zinc-600 sm:inline">
                {" "}
                · {fmtTokens(tokens)} tok
              </span>
            )}
          </span>
          <button
            onClick={onClose}
            aria-label="Close crew view"
            className="rounded-md p-1 text-zinc-400 transition-all duration-150 hover:bg-white/10 hover:text-white motion-safe:hover:rotate-90 motion-reduce:transition-none"
          >
            <X className="size-5" />
          </button>
        </div>
      </div>

      {/* stage + tool transitions are announced for screen readers */}
      <p aria-live="polite" role="status" className="sr-only">
        {announcement ||
          (activeKeys.length
            ? `Crew working on ${activeKeys.map((k) => STAGE_LABELS[k]).join(" and ")}`
            : "Crew idle")}
      </p>

      <div className="scroll-clean min-h-0 flex-1 space-y-4 overflow-y-auto p-6">
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
                    aria-label={`${STAGE_LABELS[key]} workflow`}
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
        </div>

        {sessionQuiet && (
          <p className="text-center text-xs text-zinc-500">
            {doneCount > 0
              ? "Nothing running right now. Click a stage to see how it works."
              : "Your crew reports for duty when you start a stage."}
          </p>
        )}

        {/* ── per-stage workflow panels: expanded sub-graph OR summary chip.
         * Finished paths stay fully rendered when expanded — collapse only
         * folds them to a compact summary that re-expands on click. ── */}
        {STAGE_ORDER.map((key) => {
          const st = statusOf(key);
          const stageTools = tools[key];
          const toolCount = Object.values(stageTools).filter(
            (t) => t.status !== "run"
          ).length;
          const anyData =
            Object.keys(stageTools).length > 0 || trail[key].length > 0;
          const isOpen = openPanels.includes(key);
          const cost = stageCost(key);
          const Icon = STAGE_ICONS[key];

          // nothing to say about untouched pending stages
          if (!isOpen && !anyData && st === "pending") return null;

          if (!isOpen) {
            // compact summary chip — "Storyboard ✓ · 4 tools · $0.38"
            return (
              <button
                key={key}
                onClick={() => togglePanel(key)}
                aria-expanded={false}
                className="flex w-full items-center gap-2 rounded-xl border border-white/10 bg-white/[0.02] px-3 py-2 text-left transition-colors duration-150 hover:border-white/20 motion-reduce:transition-none"
              >
                <Icon className="size-4 text-zinc-400" />
                <span className="text-sm font-medium">{STAGE_LABELS[key]}</span>
                {st === "done" && <Check className="size-3.5 text-ok" />}
                {st === "failed" && <X className="size-3.5 text-amber-300" />}
                {st === "active" &&
                  (reduced ? (
                    <span className="h-2 w-2 rounded-full bg-violet-400" />
                  ) : (
                    <Loader2 className="size-3.5 animate-spin text-violet-300" />
                  ))}
                <span className="text-[11px] text-zinc-500">
                  {toolCount > 0 &&
                    `· ${toolCount} tool${toolCount === 1 ? "" : "s"} `}
                  {cost > 0 && `· $${cost.toFixed(2)}`}
                </span>
                <ChevronDown className="ml-auto size-3.5 text-zinc-500" />
              </button>
            );
          }

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
                  aria-expanded
                  aria-label={`Collapse ${STAGE_LABELS[key]} workflow`}
                  className="ml-auto rounded-md p-1 text-zinc-500 transition-colors duration-150 hover:bg-white/10 hover:text-white motion-reduce:transition-none"
                >
                  <ChevronDown className="size-3.5 rotate-180" />
                </button>
              </div>

              {/* the workflow sub-graph */}
              <div className="px-3 pb-2 pt-3">
                <StageToolGraph stage={key} live={stageTools} reduced={reduced} />
                {STAGE_TOOLS[key].some((t) => t.run) && (
                  <p className="mt-2 text-[10px] text-zinc-600">
                    Dashed steps run only when needed or when you press their
                    button. Idle is healthy — hover one to see what triggers it.
                  </p>
                )}
                {Object.keys(stageTools).length === 0 && (
                  <p className="mt-2 text-center text-[10px] text-zinc-600">
                    {progress?.[key]
                      ? "Finished before this session — this is the machinery it ran."
                      : "These tools light up as the stage runs."}
                  </p>
                )}
              </div>

              {/* the event log under the graph — the full story, kept visible */}
              {trail[key].length > 0 && (
                <div className="scroll-clean max-h-36 overflow-y-auto border-t border-white/[0.06] px-3 py-2">
                  {trail[key].map((e, i) => (
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
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}
