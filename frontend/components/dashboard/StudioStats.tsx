"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Check,
  Clapperboard,
  Link2,
  MessageSquare,
  PenLine,
  Scissors,
  Users,
  Wallet,
  X,
  type LucideIcon,
} from "lucide-react";
import { Skeleton } from "@/components/shared/Skeleton";
import { cn } from "@/lib/utils";
import api from "@/lib/api";
import { useCountUp } from "@/hooks/useCountUp";
import { useReducedMotion } from "@/hooks/useReducedMotion";
import { useProjectsOverview } from "@/hooks/useProjects";
import { fmtFilm } from "@/components/dashboard/format";

interface DayStat {
  date: string;
  clips: number;
  spent: number;
}

interface StudioStatsData {
  days: DayStat[];
  agents: {
    agent: string;
    runs: number;
    avg_confidence: number | null;
    dramas?: number;
    last_run?: string | null;
  }[];
  cost_split: Record<string, number>;
  totals: {
    dramas: number;
    clips: number;
    film_seconds: number;
    spent_usd: number;
  };
}

/* ── your crew: reframe raw agent telemetry as who did what ─────────── */

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** Backend timestamps are naive UTC — anchor before diffing. */
function agoLabel(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const t = new Date(
    /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`
  ).getTime();
  if (Number.isNaN(t)) return null;
  const mins = Math.max(0, Math.round((Date.now() - t) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

const CREW: Record<
  string,
  {
    icon: LucideIcon;
    role: string;
    did: (n: number) => string;
    detail: (dramas: number) => string;
  }
> = {
  narrative_judge: {
    icon: Scissors,
    role: "Editor / Judge",
    did: (n) => `Reviewed ${plural(n, "draft")} before any spend`,
    detail: (d) => `Judged drafts on ${plural(d, "drama")}`,
  },
  script_reviser: {
    icon: PenLine,
    role: "Reviser",
    did: (n) => `Rewrote ${plural(n, "draft")} with the judge's notes`,
    detail: (d) => `Reworked scripts on ${plural(d, "drama")}`,
  },
  clarification: {
    icon: MessageSquare,
    role: "Script Doctor",
    did: (n) => `Checked ${plural(n, "script")} for ambiguity`,
    detail: (d) => `Raised questions on ${plural(d, "drama")}`,
  },
  style_casting: {
    icon: Users,
    role: "Casting",
    did: (n) => `Locked faces, outfits and voices in ${plural(n, "run")}`,
    detail: (d) => `Cast ${plural(d, "drama")}`,
  },
  continuity: {
    icon: Link2,
    role: "Continuity",
    did: (n) => `Checked ${plural(n, "shot")} for face and scene drift`,
    detail: (d) => `Watched ${plural(d, "drama")} for drift`,
  },
  budget_allocator: {
    icon: Wallet,
    role: "Producer",
    did: (n) => `Fitted the spend plan ${n} time${n === 1 ? "" : "s"}`,
    detail: (d) => `Fitted budgets on ${plural(d, "drama")}`,
  },
  Showrunner: {
    icon: Clapperboard,
    role: "Showrunner",
    did: (n) => `Answered ${plural(n, "question")} about your dramas`,
    detail: (d) => `Chatted across ${plural(d, "drama")}`,
  },
};

function crewOf(agent: string) {
  return (
    CREW[agent] ?? {
      icon: Clapperboard,
      role: agent.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      did: (n: number) => plural(n, "report"),
      detail: (d: number) => `Worked on ${plural(d, "drama")}`,
    }
  );
}

/** Health tier: quiet when reliable, loud only when something needs a look. */
function health(conf: number | null) {
  if (conf === null) return null;
  const pct = Math.round(Math.min(Math.max(conf, 0), 1) * 100);
  if (pct >= 90) return { pct, tier: "ok" as const };
  if (pct >= 70) return { pct, tier: "good" as const };
  return { pct, tier: "alert" as const };
}

const TIER_RANK = { alert: 0, good: 1, ok: 2 };

/* ── where budget went: one cohesive cool ramp, no alarm colors ──────── */

const SPLIT_ORDER: {
  key: string;
  label: string;
  color: string;
  phrase: string;
  noun: string;
}[] = [
  {
    key: "video",
    label: "Video",
    color: "bg-violet-500",
    phrase: "video generation",
    noun: "Video generation",
  },
  {
    key: "image",
    label: "Image",
    color: "bg-violet-300",
    phrase: "bible plates and posters",
    noun: "Image generation",
  },
  {
    key: "llm",
    label: "LLM",
    color: "bg-blue-400",
    phrase: "writing and analysis",
    noun: "Writing and analysis",
  },
];

function cellTone(clips: number): string {
  if (clips <= 0) return "bg-white/5";
  if (clips === 1) return "bg-violet-900";
  if (clips <= 3) return "bg-violet-700";
  return "bg-violet-500";
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
      {children}
    </h3>
  );
}

function CountNum({
  value,
  format,
}: {
  value: number;
  format?: (v: number) => string;
}) {
  const reduced = useReducedMotion();
  const v = useCountUp(value, reduced);
  return <>{format ? format(v) : Math.round(v)}</>;
}

/** Shared dark tooltip chrome. */
const TIP =
  "pointer-events-none whitespace-nowrap rounded-md border border-white/10 bg-[#161122] px-2 py-1 text-[10px] text-zinc-300 shadow-lg";

const DAY_LABELS = ["", "Mon", "", "Wed", "", "Fri", ""];

/** GitHub-style activity grid: 26 weeks of daily generation. */
function Heatmap({ days }: { days: DayStat[] }) {
  const reduced = useReducedMotion();
  // the tooltip is absolute inside this wrapper — fixed positioning breaks
  // here because the card-rise ancestor keeps a transform (forwards fill)
  const wrapRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<{
    wi: number;
    di: number;
    x: number;
    y: number;
    label: string;
  } | null>(null);

  const byDate = new Map(days.map((d) => [d.date, d]));
  const today = new Date();
  const start = new Date(today);
  start.setDate(start.getDate() - start.getDay() - 25 * 7); // Sunday, 26 weeks back

  const weeks: Date[][] = [];
  const cursor = new Date(start);
  while (cursor <= today) {
    const week: Date[] = [];
    for (let i = 0; i < 7; i++) {
      week.push(new Date(cursor));
      cursor.setDate(cursor.getDate() + 1);
    }
    weeks.push(week);
  }

  // label a column when its month differs from the previous column's
  const monthLabels = weeks.map((week, wi) => {
    const m = week[0].getMonth();
    const prev = wi > 0 ? weeks[wi - 1][0].getMonth() : -1;
    return m !== prev
      ? week[0].toLocaleString("en", { month: "short" })
      : null;
  });

  const activeDays = days.filter((d) => d.clips > 0).length;

  return (
    <div ref={wrapRef} className="relative">
      <div className="mb-1 flex gap-[3px] pl-[30px]">
        {monthLabels.map((label, i) => (
          <span
            key={i}
            className="w-2.5 shrink-0 overflow-visible whitespace-nowrap text-[10px] leading-none text-zinc-500"
          >
            {label ?? ""}
          </span>
        ))}
      </div>
      <div className="flex">
        <div className="mr-1 flex w-[26px] shrink-0 flex-col gap-[3px]">
          {DAY_LABELS.map((d, i) => (
            <span
              key={i}
              className="flex h-2.5 items-center text-[10px] leading-none text-zinc-500"
            >
              {d}
            </span>
          ))}
        </div>
        <div
          className="flex gap-[3px] overflow-x-auto pb-1"
          onMouseLeave={() => setHover(null)}
        >
          {weeks.map((week, wi) => (
            <div key={wi} className="flex flex-col gap-[3px]">
              {week.map((day, di) => {
                const key = day.toISOString().slice(0, 10);
                const stat = byDate.get(key);
                const future = day > today;
                const isHover = hover?.wi === wi && hover?.di === di;
                // crosshair: its own row and column dim so the day pops
                const inCross =
                  !future &&
                  hover &&
                  !isHover &&
                  (hover.wi === wi || hover.di === di);
                return (
                  <span
                    key={key}
                    onMouseEnter={
                      future
                        ? undefined
                        : (e) => {
                            const wrap = wrapRef.current;
                            if (!wrap) return;
                            const r = e.currentTarget.getBoundingClientRect();
                            const w = wrap.getBoundingClientRect();
                            setHover({
                              wi,
                              di,
                              // clamp so the centered tooltip stays inside the drawer
                              x: Math.min(
                                w.width - 64,
                                Math.max(64, r.left - w.left + r.width / 2)
                              ),
                              y: r.top - w.top,
                              label: `${stat?.clips ?? 0} clips · $${(
                                stat?.spent ?? 0
                              ).toFixed(2)} · ${day.toLocaleDateString("en", {
                                month: "short",
                                day: "numeric",
                              })}`,
                            });
                          }
                    }
                    className={cn(
                      "h-2.5 w-2.5 rounded-[2px] transition-[transform,opacity] duration-150 motion-reduce:transition-none",
                      future ? "opacity-0" : cellTone(stat?.clips ?? 0),
                      isHover && "relative z-10 ring-1 ring-violet-400",
                      isHover && !reduced && "scale-[1.4]",
                      inCross && "opacity-50"
                    )}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
      {hover && (
        <div
          className={cn(TIP, "absolute z-20 -translate-x-1/2 -translate-y-full")}
          style={{ left: hover.x, top: hover.y - 6 }}
        >
          {hover.label}
        </div>
      )}
      <div className="mt-2 flex items-center justify-end gap-1.5 text-[10px] text-zinc-500">
        Less
        {["bg-white/5", "bg-violet-900", "bg-violet-700", "bg-violet-500"].map(
          (c) => (
            <span key={c} className={cn("h-2.5 w-2.5 rounded-[2px]", c)} />
          )
        )}
        More
      </div>
      {activeDays < 10 && (
        <p className="mt-2 text-xs text-zinc-500">
          Your activity grid fills in as you generate more.
        </p>
      )}
    </div>
  );
}

/** Sum clips/spend over the [from, to) day window (offsets back from today). */
function windowSum(days: DayStat[], fromDaysAgo: number, toDaysAgo: number) {
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  let clips = 0;
  let spent = 0;
  for (const d of days) {
    const age = Math.floor(
      (now.getTime() - new Date(d.date + "T00:00:00").getTime()) / 86400000
    );
    if (age >= toDaysAgo && age < fromDaysAgo) {
      clips += d.clips;
      spent += d.spent;
    }
  }
  return { clips, spent };
}

export function StudioStatsDrawer({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["projects", "stats"],
    enabled: open,
    queryFn: async () => {
      const res = await api.get("/api/projects/stats");
      return res.data as StudioStatsData;
    },
  });
  // shares the dashboard's cached overview — powers the "done vs drafts" hover
  const { data: overview } = useProjectsOverview();
  const [legendHover, setLegendHover] = useState<string | null>(null);
  const [barHover, setBarHover] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  if (!open) return null;

  const splitTotal = SPLIT_ORDER.reduce(
    (sum, s) => sum + (data?.cost_split[s.key] ?? 0),
    0
  );
  const pctLabel = (v: number) => {
    const p = splitTotal > 0 ? (v / splitTotal) * 100 : 0;
    return p > 0 && p < 1 ? "<1%" : `${Math.round(p)}%`;
  };
  const biggest =
    splitTotal > 0
      ? SPLIT_ORDER.reduce((best, s) =>
          (data?.cost_split[s.key] ?? 0) > (data?.cost_split[best.key] ?? 0)
            ? s
            : best
        )
      : null;
  // stacked-bar segments with cumulative midpoints for the hover tooltip
  let cum = 0;
  const segments = SPLIT_ORDER.flatMap((s) => {
    const v = data?.cost_split[s.key] ?? 0;
    if (v <= 0 || splitTotal <= 0) return [];
    const width = (v / splitTotal) * 100;
    const seg = { ...s, value: v, width, mid: cum + width / 2 };
    cum += width;
    return [seg];
  });
  const splitHover = barHover ?? legendHover;
  const barSeg = segments.find((s) => s.key === barHover);
  const hoveredSplit = SPLIT_ORDER.find((s) => s.key === splitHover);

  // this week vs last week, from the daily series
  const thisWeek = data ? windowSum(data.days, 7, 0) : { clips: 0, spent: 0 };
  const lastWeek = data ? windowSum(data.days, 14, 7) : { clips: 0, spent: 0 };
  const clipDelta = thisWeek.clips - lastWeek.clips;
  const perClipSecs =
    data && data.totals.clips > 0
      ? data.totals.film_seconds / data.totals.clips
      : 5;
  // last 4 weeks of clips, oldest first, for the chip's hover sparkline
  const weeksSeries = data
    ? [3, 2, 1, 0].map((i) => windowSum(data.days, 7 * (i + 1), 7 * i).clips)
    : [];
  const maxWeek = Math.max(1, ...weeksSeries);

  // problems first, then by involvement
  const crew = data
    ? [...data.agents].sort((a, b) => {
        const ra = TIER_RANK[health(a.avg_confidence)?.tier ?? "ok"];
        const rb = TIER_RANK[health(b.avg_confidence)?.tier ?? "ok"];
        return ra !== rb ? ra - rb : b.runs - a.runs;
      })
    : [];
  const crewRuns = crew.reduce((sum, a) => sum + a.runs, 0);
  const crewFlagged = crew.filter((a) => {
    const h = health(a.avg_confidence);
    return h !== null && h.tier !== "ok";
  }).length;

  // hover sub-labels for the totals cards, precomputed
  const doneCount = overview?.projects.filter(
    (p) => p.status === "complete"
  ).length;
  const totalsSubs = data
    ? {
        Dramas:
          doneCount !== undefined
            ? `${doneCount} done · ${plural(
                Math.max(0, data.totals.dramas - doneCount),
                "draft"
              )}`
            : "on your shelf",
        Clips: `across ${plural(data.totals.dramas, "drama")}`,
        Runtime:
          data.totals.clips > 0
            ? `avg ${fmtFilm(perClipSecs)} per clip`
            : "no clips yet",
        Spent:
          data.totals.dramas > 0
            ? `≈ $${(data.totals.spent_usd / data.totals.dramas).toFixed(
                2
              )} per drama`
            : "nothing yet",
      }
    : ({} as Record<string, string>);

  const sections: React.ReactNode[] = data
    ? [
        /* 1 — headline totals: the boldest thing in the drawer */
        <section key="totals">
          <div className="grid grid-cols-4 gap-2">
            {(
              [
                ["Dramas", <CountNum key="d" value={data.totals.dramas} />],
                ["Clips", <CountNum key="c" value={data.totals.clips} />],
                [
                  "Runtime",
                  <CountNum
                    key="r"
                    value={data.totals.film_seconds}
                    format={fmtFilm}
                  />,
                ],
                [
                  "Spent",
                  <CountNum
                    key="s"
                    value={data.totals.spent_usd}
                    format={(v) => `$${v.toFixed(2)}`}
                  />,
                ],
              ] as const
            ).map(([label, node]) => (
              <div
                key={label}
                className="group rounded-xl border border-white/[0.08] bg-white/[0.02] px-2 pb-2.5 pt-4 text-center transition-all duration-150 hover:border-white/15 motion-safe:hover:-translate-y-0.5 motion-reduce:transition-none"
              >
                <p className="text-2xl font-semibold tabular-nums text-foreground">
                  {node}
                </p>
                <p className="mt-1 text-[10px] uppercase tracking-widest text-zinc-500">
                  {label}
                </p>
                {/* reserved slot — fades in on hover, never reflows */}
                <p className="mt-0.5 h-3.5 truncate text-[10px] leading-[14px] text-zinc-600 opacity-0 transition-opacity duration-150 group-hover:opacity-100 motion-reduce:transition-none">
                  {totalsSubs[label]}
                </p>
              </div>
            ))}
          </div>
        </section>,

        /* 2 — this week, with change vs last week */
        <section key="week" className="space-y-3">
          <SectionTitle>This week</SectionTitle>
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-zinc-400">
            <span>
              <span className="font-medium tabular-nums text-zinc-200">
                {thisWeek.clips}
              </span>{" "}
              clips
            </span>
            <span className="text-zinc-700">·</span>
            <span>
              <span className="font-medium tabular-nums text-zinc-200">
                {fmtFilm(thisWeek.clips * perClipSecs)}
              </span>{" "}
              generated
            </span>
            <span className="text-zinc-700">·</span>
            <span>
              <span className="font-medium tabular-nums text-zinc-200">
                ${thisWeek.spent.toFixed(2)}
              </span>{" "}
              spent
            </span>
            {(thisWeek.clips > 0 || lastWeek.clips > 0) && clipDelta !== 0 && (
              <span
                className={cn(
                  "group/chip relative cursor-default rounded-full px-2 py-0.5 text-[10px] font-medium tabular-nums",
                  clipDelta > 0
                    ? "bg-emerald-500/10 text-emerald-400"
                    : "bg-red-500/10 text-red-400"
                )}
              >
                {clipDelta > 0 ? "▲" : "▼"} {Math.abs(clipDelta)}{" "}
                {clipDelta > 0 ? "more" : "fewer"} clips than last week
                {/* hover: last 4 weeks at a glance — floats, no layout shift */}
                <span className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1.5 -translate-x-1/2 rounded-md border border-white/10 bg-[#161122] px-2.5 py-2 opacity-0 shadow-lg transition-opacity duration-150 group-hover/chip:opacity-100 motion-reduce:transition-none">
                  <span className="flex h-6 items-end justify-center gap-1">
                    {weeksSeries.map((c, i) => (
                      <span
                        key={i}
                        className={cn(
                          "w-1.5 rounded-sm",
                          i === weeksSeries.length - 1
                            ? "bg-violet-400"
                            : "bg-white/20"
                        )}
                        style={{
                          height: `${Math.max(2, (c / maxWeek) * 24)}px`,
                        }}
                      />
                    ))}
                  </span>
                  <span className="mt-1 block whitespace-nowrap text-center text-[9px] font-normal text-zinc-500">
                    clips · last 4 weeks
                  </span>
                </span>
              </span>
            )}
          </p>
        </section>,

        /* 3 — where budget went */
        <section key="budget" className="space-y-3">
          <SectionTitle>Where budget went</SectionTitle>
          {splitTotal <= 0 ? (
            <p className="text-xs text-zinc-500">Nothing spent yet.</p>
          ) : (
            <>
              <div className="relative">
                <div className="flex h-2.5 gap-px overflow-hidden rounded-full bg-white/5">
                  {segments.map((s) => (
                    <div
                      key={s.key}
                      onMouseEnter={() => setBarHover(s.key)}
                      onMouseLeave={() => setBarHover(null)}
                      className={cn(
                        s.color,
                        "transition-opacity duration-150 motion-reduce:transition-none",
                        splitHover && splitHover !== s.key && "opacity-40"
                      )}
                      style={{ width: `${s.width}%` }}
                    />
                  ))}
                </div>
                {barSeg && (
                  <div
                    className={cn(
                      TIP,
                      "absolute bottom-full z-10 mb-1.5 -translate-x-1/2"
                    )}
                    style={{
                      left: `${Math.min(85, Math.max(15, barSeg.mid))}%`,
                    }}
                  >
                    {barSeg.label} · ${barSeg.value.toFixed(2)} ·{" "}
                    {pctLabel(barSeg.value)} of spend
                  </div>
                )}
              </div>
              <div className="space-y-0.5">
                {segments.map((s) => (
                  <div
                    key={s.key}
                    onMouseEnter={() => setLegendHover(s.key)}
                    onMouseLeave={() => setLegendHover(null)}
                    className={cn(
                      "-mx-1.5 flex items-center gap-2 rounded-md px-1.5 py-1 text-xs transition-all duration-150 motion-reduce:transition-none",
                      splitHover === s.key
                        ? "bg-white/[0.04] font-medium text-zinc-200"
                        : "text-zinc-400",
                      splitHover && splitHover !== s.key && "opacity-40"
                    )}
                  >
                    <span className={cn("h-2 w-2 rounded-[2px]", s.color)} />
                    {s.label}
                    <span className="ml-auto w-16 text-right tabular-nums text-zinc-300">
                      $<CountNum value={s.value} format={(x) => x.toFixed(2)} />
                    </span>
                    <span className="w-10 text-right tabular-nums text-zinc-600">
                      {pctLabel(s.value)}
                    </span>
                  </div>
                ))}
              </div>
              <p className="text-[11px] text-zinc-500">
                {hoveredSplit
                  ? `${hoveredSplit.noun} is ${pctLabel(
                      data.cost_split[hoveredSplit.key] ?? 0
                    )} of your spend.`
                  : biggest
                    ? `Most of your budget goes to ${biggest.phrase}.`
                    : ""}
              </p>
            </>
          )}
        </section>,

        /* 4 — activity heatmap */
        <section key="activity" className="space-y-3 opacity-90">
          <SectionTitle>Generation activity · 26 weeks</SectionTitle>
          <Heatmap days={data.days} />
        </section>,

        /* 5 — your crew */
        <section key="crew" className="space-y-3">
          <SectionTitle>Your crew</SectionTitle>
          {crew.length === 0 ? (
            <p className="text-xs text-zinc-500">
              Your crew reports for duty once a drama runs the pipeline.
            </p>
          ) : (
            <>
              <p className="text-xs text-zinc-500">
                Your crew ran {plural(crewRuns, "task")}
                {crewFlagged > 0
                  ? ` · ${crewFlagged} need${
                      crewFlagged === 1 ? "s" : ""
                    } a look.`
                  : ". Everything ran clean."}
              </p>
              <div className="space-y-1">
                {crew.map((a) => {
                  const member = crewOf(a.agent);
                  const h = health(a.avg_confidence);
                  const Icon = member.icon;
                  const parts: string[] = [];
                  const ago = agoLabel(a.last_run);
                  if (ago) parts.push(`Last ran ${ago}`);
                  if (typeof a.dramas === "number" && a.dramas > 0)
                    parts.push(member.detail(a.dramas));
                  if (parts.length === 0 && h)
                    parts.push(`Avg confidence ${h.pct}%`);
                  const detail = parts.join(" · ");
                  return (
                    // TODO: deep-link to this agent's activity feed once a destination exists
                    <div
                      key={a.agent}
                      className={cn(
                        "group -mx-2 rounded-lg border px-2 py-2 transition-colors duration-150 motion-reduce:transition-none",
                        h?.tier === "alert"
                          ? "border-red-400/20 bg-red-500/5 hover:bg-red-500/[0.08]"
                          : "border-transparent hover:bg-white/[0.03]"
                      )}
                    >
                      <div className="flex items-start gap-3">
                        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03]">
                          <Icon className="size-4 text-zinc-400 transition-colors duration-150 group-hover:text-violet-300 motion-reduce:transition-none" />
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-zinc-200">
                            {member.role}
                          </p>
                          <p className="truncate text-xs text-zinc-500">
                            {member.did(a.runs)}
                          </p>
                          {detail && (
                            <div className="max-h-0 overflow-hidden opacity-0 transition-all duration-150 group-hover:max-h-6 group-hover:opacity-100 motion-reduce:transition-none">
                              <p className="truncate pt-1 text-[11px] text-zinc-600">
                                {detail}
                              </p>
                            </div>
                          )}
                        </div>
                        {h && (
                          <div
                            className="flex shrink-0 items-center gap-1.5 pt-1"
                            title="Average confidence this crew member reported for its own decisions. For the Reviser this tracks the judge scores of drafts it was asked to fix, so a low number means hard drafts, not a broken agent."
                          >
                            {h.tier === "ok" ? (
                              <Check
                                aria-label="Reliable"
                                className="size-3.5 text-emerald-400"
                              />
                            ) : (
                              <>
                                <span
                                  className={cn(
                                    "h-1.5 w-1.5 rounded-full",
                                    h.tier === "good"
                                      ? "bg-amber-400"
                                      : "bg-red-400"
                                  )}
                                />
                                <span
                                  className={cn(
                                    "text-[10px] font-medium",
                                    h.tier === "good"
                                      ? "text-amber-400/90"
                                      : "text-red-400/90"
                                  )}
                                >
                                  {h.tier === "good"
                                    ? "Solid"
                                    : "Low confidence"}
                                </span>
                                <span className="text-[10px] tabular-nums text-zinc-600">
                                  {h.pct}%
                                </span>
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </section>,
      ]
    : [];

  return (
    <div className="fixed inset-0 z-50">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
      />
      <aside
        role="dialog"
        aria-label="Studio stats"
        className="absolute right-0 top-0 h-full w-[480px] max-w-full space-y-8 overflow-y-auto border-l border-white/10 bg-[#0b0912] p-6 shadow-2xl duration-300 animate-in slide-in-from-right scroll-clean"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold tracking-tight">Studio stats</h2>
          <button
            aria-label="Close"
            onClick={() => onOpenChange(false)}
            className="rounded-md p-1 text-zinc-400 transition-all duration-150 hover:bg-white/10 hover:text-white motion-safe:hover:rotate-90 motion-reduce:transition-none"
          >
            <X className="size-5" />
          </button>
        </div>

        {isLoading || !data ? (
          <div className="space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-16 rounded-lg" />
            ))}
          </div>
        ) : (
          sections.map((s, i) => (
            <div
              key={i}
              className={cn(
                "card-rise",
                i > 0 && "border-t border-white/[0.06] pt-6"
              )}
              style={{ animationDelay: `${i * 70}ms` }}
            >
              {s}
            </div>
          ))
        )}
      </aside>
    </div>
  );
}
