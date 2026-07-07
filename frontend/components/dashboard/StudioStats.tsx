"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Check,
  Clapperboard,
  Link2,
  MessageSquare,
  PenLine,
  Scissors,
  Users,
  Volume2,
  Wallet,
  X,
  type LucideIcon,
} from "lucide-react";
import { Skeleton } from "@/components/shared/Skeleton";
import { cn } from "@/lib/utils";
import api from "@/lib/api";
import { useCountUp } from "@/hooks/useCountUp";
import { useReducedMotion } from "@/hooks/useReducedMotion";
import { fmtFilm } from "@/components/dashboard/format";

interface DayStat {
  date: string;
  clips: number;
  spent: number;
}

interface StudioStatsData {
  days: DayStat[];
  agents: { agent: string; runs: number; avg_confidence: number | null }[];
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

const CREW: Record<
  string,
  { icon: LucideIcon; role: string; did: (n: number) => string }
> = {
  narrative_judge: {
    icon: Scissors,
    role: "Editor / Judge",
    did: (n) => `Reviewed ${plural(n, "draft")} before any spend`,
  },
  script_reviser: {
    icon: PenLine,
    role: "Reviser",
    did: (n) => `Rewrote ${plural(n, "draft")} with the judge's notes`,
  },
  clarification: {
    icon: MessageSquare,
    role: "Script Doctor",
    did: (n) => `Checked ${plural(n, "script")} for ambiguity`,
  },
  style_casting: {
    icon: Users,
    role: "Casting",
    did: (n) => `Locked faces, outfits and voices in ${plural(n, "run")}`,
  },
  continuity: {
    icon: Link2,
    role: "Continuity",
    did: (n) => `Checked ${plural(n, "shot")} for face and scene drift`,
  },
  budget_allocator: {
    icon: Wallet,
    role: "Producer",
    did: (n) => `Fitted the spend plan ${n} time${n === 1 ? "" : "s"}`,
  },
  audio_continuity: {
    icon: Volume2,
    role: "Audio",
    did: (n) => `Voiced dialogue in ${plural(n, "run")}`,
  },
  Showrunner: {
    icon: Clapperboard,
    role: "Showrunner",
    did: (n) => `Answered ${plural(n, "question")} about your dramas`,
  },
};

function crewOf(agent: string) {
  return (
    CREW[agent] ?? {
      icon: Clapperboard,
      role: agent.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      did: (n: number) => plural(n, "report"),
    }
  );
}

/** Health of a crew member, in words first, numbers second. */
function health(conf: number | null) {
  if (conf === null) return null;
  const pct = Math.round(Math.min(Math.max(conf, 0), 1) * 100);
  if (pct >= 90) return { pct, word: "Reliable", dot: "bg-emerald-400", text: "text-emerald-400/90" };
  if (pct >= 70) return { pct, word: "Good", dot: "bg-amber-400", text: "text-amber-400/90" };
  return { pct, word: "Needs attention", dot: "bg-red-400", text: "text-red-400/90" };
}

/* ── where budget went: one cohesive cool ramp, no alarm colors ──────── */

const SPLIT_ORDER: { key: string; label: string; color: string; phrase: string }[] = [
  { key: "video", label: "Video", color: "bg-violet-500", phrase: "video generation" },
  { key: "image", label: "Image", color: "bg-violet-300", phrase: "bible plates and posters" },
  { key: "llm", label: "LLM", color: "bg-blue-400", phrase: "writing and analysis" },
  { key: "tts", label: "Voice", color: "bg-zinc-500", phrase: "voice synthesis" },
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

const DAY_LABELS = ["", "Mon", "", "Wed", "", "Fri", ""];

/** GitHub-style activity grid: 26 weeks of daily generation. */
function Heatmap({ days }: { days: DayStat[] }) {
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
    <div>
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
        <div className="flex gap-[3px] overflow-x-auto pb-1">
          {weeks.map((week, wi) => (
            <div key={wi} className="flex flex-col gap-[3px]">
              {week.map((day) => {
                const key = day.toISOString().slice(0, 10);
                const stat = byDate.get(key);
                const future = day > today;
                return (
                  <span
                    key={key}
                    title={
                      future
                        ? undefined
                        : `${key}: ${stat?.clips ?? 0} clips · $${(
                            stat?.spent ?? 0
                          ).toFixed(2)}`
                    }
                    className={cn(
                      "h-2.5 w-2.5 rounded-[2px]",
                      future ? "opacity-0" : cellTone(stat?.clips ?? 0)
                    )}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
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
  const biggest =
    splitTotal > 0
      ? SPLIT_ORDER.reduce((best, s) =>
          (data?.cost_split[s.key] ?? 0) > (data?.cost_split[best.key] ?? 0)
            ? s
            : best
        )
      : null;

  // this week vs last week, from the daily series
  const thisWeek = data ? windowSum(data.days, 7, 0) : { clips: 0, spent: 0 };
  const lastWeek = data ? windowSum(data.days, 14, 7) : { clips: 0, spent: 0 };
  const clipDelta = thisWeek.clips - lastWeek.clips;
  const perClipSecs =
    data && data.totals.clips > 0
      ? data.totals.film_seconds / data.totals.clips
      : 5;

  const crew = data
    ? [...data.agents].sort((a, b) => b.runs - a.runs)
    : [];

  const sections: React.ReactNode[] = data
    ? [
        /* 1 — headline totals */
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
                className="rounded-xl border border-white/[0.08] bg-white/[0.02] px-2 py-4 text-center"
              >
                <p className="text-xl font-semibold tabular-nums text-foreground">
                  {node}
                </p>
                <p className="mt-1 text-[10px] uppercase tracking-widest text-zinc-500">
                  {label}
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
                  "rounded-full px-2 py-0.5 text-[10px] font-medium tabular-nums",
                  clipDelta > 0
                    ? "bg-emerald-500/10 text-emerald-400"
                    : "bg-red-500/10 text-red-400"
                )}
              >
                {clipDelta > 0 ? "▲" : "▼"} {Math.abs(clipDelta)} vs last week
              </span>
            )}
          </p>
        </section>,

        /* 3 — your crew */
        <section key="crew" className="space-y-3">
          <SectionTitle>Your crew</SectionTitle>
          {crew.length === 0 ? (
            <p className="text-xs text-zinc-500">
              Your crew reports for duty once a drama runs the pipeline.
            </p>
          ) : (
            <div className="space-y-4">
              {crew.map((a) => {
                const member = crewOf(a.agent);
                const h = health(a.avg_confidence);
                const Icon = member.icon;
                return (
                  <div key={a.agent} className="space-y-1.5">
                    <div className="flex items-start gap-3">
                      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03]">
                        <Icon className="size-4 text-zinc-400" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-zinc-200">
                          {member.role}
                        </p>
                        <p className="truncate text-xs text-zinc-500">
                          {member.did(a.runs)}
                        </p>
                      </div>
                      {h && (
                        <div className="shrink-0 text-right">
                          <p className="flex items-center justify-end gap-1.5">
                            <span className={cn("h-1.5 w-1.5 rounded-full", h.dot)} />
                            <span className={cn("text-[10px] font-medium", h.text)}>
                              {h.word}
                            </span>
                          </p>
                          {h.pct >= 100 ? (
                            <Check className="ml-auto mt-0.5 size-3 text-zinc-600" />
                          ) : (
                            <p className="mt-0.5 text-[10px] tabular-nums text-zinc-600">
                              {h.pct}%
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                    {/* secondary: a whisper of a confidence track */}
                    <div className="ml-11 h-1 overflow-hidden rounded-full bg-white/[0.04]">
                      <div
                        className="h-full rounded-full bg-violet-500/40 transition-all duration-700"
                        style={{
                          width: `${((a.avg_confidence ?? 0) * 100).toFixed(0)}%`,
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>,

        /* 4 — where budget went */
        <section key="budget" className="space-y-3">
          <SectionTitle>Where budget went</SectionTitle>
          {splitTotal <= 0 ? (
            <p className="text-xs text-zinc-500">Nothing spent yet.</p>
          ) : (
            <>
              <div className="flex h-2.5 gap-px overflow-hidden rounded-full bg-white/5">
                {SPLIT_ORDER.map((s) => {
                  const v = data.cost_split[s.key] ?? 0;
                  if (v <= 0) return null;
                  return (
                    <div
                      key={s.key}
                      className={s.color}
                      style={{ width: `${(v / splitTotal) * 100}%` }}
                    />
                  );
                })}
              </div>
              <div className="space-y-1.5">
                {SPLIT_ORDER.map((s) => {
                  const v = data.cost_split[s.key] ?? 0;
                  if (v <= 0) return null;
                  return (
                    <div
                      key={s.key}
                      className="flex items-center gap-2 text-xs text-zinc-400"
                    >
                      <span className={cn("h-2 w-2 rounded-[2px]", s.color)} />
                      {s.label}
                      <span className="ml-auto tabular-nums text-zinc-300">
                        $<CountNum value={v} format={(x) => x.toFixed(2)} />
                      </span>
                      <span className="w-10 text-right tabular-nums text-zinc-600">
                        {Math.round((v / splitTotal) * 100)}%
                      </span>
                    </div>
                  );
                })}
              </div>
              {biggest && (
                <p className="text-xs text-zinc-500">
                  Most of your budget goes to {biggest.phrase}.
                </p>
              )}
            </>
          )}
        </section>,

        /* 5 — activity heatmap, de-emphasized at the bottom */
        <section key="activity" className="space-y-3 opacity-90">
          <SectionTitle>Generation activity · 26 weeks</SectionTitle>
          <Heatmap days={data.days} />
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
        className="absolute right-0 top-0 h-full w-[480px] max-w-full space-y-9 overflow-y-auto border-l border-white/10 bg-[#0b0912] p-6 shadow-2xl duration-300 animate-in slide-in-from-right scroll-clean"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold tracking-tight">Studio stats</h2>
          <button
            aria-label="Close"
            onClick={() => onOpenChange(false)}
            className="rounded-md p-1 text-zinc-400 transition-colors hover:text-white"
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
              className="card-rise"
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
