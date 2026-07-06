"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
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

const AGENT_LABELS: Record<string, string> = {
  continuity: "Continuity",
  budget_allocator: "Budget Allocator",
  audio_continuity: "Audio Continuity",
  style_casting: "Style / Casting",
  narrative_judge: "Narrative Judge",
  clarification: "Clarification",
};

const SPLIT_ORDER: { key: string; label: string; color: string }[] = [
  { key: "video", label: "Video", color: "bg-violet-500" },
  { key: "image", label: "Image", color: "bg-pink-400" },
  { key: "llm", label: "LLM", color: "bg-blue-400" },
  { key: "tts", label: "TTS", color: "bg-zinc-500" },
];

function confTone(c: number | null): string {
  if (c === null) return "text-muted-foreground";
  if (c >= 0.9) return "text-zinc-200";
  if (c >= 0.7) return "text-amber-400";
  return "text-red-400";
}

function cellTone(clips: number): string {
  if (clips <= 0) return "bg-white/5";
  if (clips === 1) return "bg-violet-900";
  if (clips <= 3) return "bg-violet-700";
  return "bg-violet-500";
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
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
      {days.length === 0 && (
        <p className="mt-2 text-xs text-muted-foreground">
          No generation activity yet. Your first render lights this up.
        </p>
      )}
    </div>
  );
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

  return (
    <div className="fixed inset-0 z-50">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
      />
      <aside
        role="dialog"
        aria-label="Studio stats"
        className="absolute right-0 top-0 h-full w-[480px] max-w-full space-y-8 overflow-y-auto border-l border-white/10 bg-[#0b0912] p-6 shadow-2xl duration-300 animate-in slide-in-from-right"
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
          <>
            {/* activity heatmap */}
            <section className="space-y-3">
              <SectionTitle>Generation activity · 26 weeks</SectionTitle>
              <Heatmap days={data.days} />
            </section>

            {/* agent breakdown */}
            <section className="space-y-3">
              <SectionTitle>Agents</SectionTitle>
              {data.agents.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  Agent reports appear once a drama runs the pipeline.
                </p>
              ) : (
                <div className="space-y-2.5">
                  {data.agents.map((a) => (
                    <div key={a.agent} className="flex items-center gap-3">
                      <span className="w-32 shrink-0 truncate text-sm text-zinc-300">
                        {AGENT_LABELS[a.agent] ?? a.agent}
                      </span>
                      <span className="w-14 shrink-0 text-right font-mono text-[11px] text-muted-foreground">
                        <CountNum value={a.runs} /> runs
                      </span>
                      <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-white/5">
                        <div
                          className="h-full rounded-full bg-violet-500/70 transition-all duration-700"
                          style={{
                            width: `${((a.avg_confidence ?? 0) * 100).toFixed(0)}%`,
                          }}
                        />
                      </div>
                      <span
                        className={cn(
                          "w-10 shrink-0 text-right font-mono text-[11px] tabular-nums",
                          confTone(a.avg_confidence)
                        )}
                      >
                        {a.avg_confidence !== null
                          ? `${Math.round(a.avg_confidence * 100)}%`
                          : "–"}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* cost split */}
            <section className="space-y-3">
              <SectionTitle>Cost split</SectionTitle>
              {splitTotal <= 0 ? (
                <p className="text-xs text-muted-foreground">
                  Nothing spent yet.
                </p>
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
                  <div className="flex flex-wrap gap-x-4 gap-y-1.5">
                    {SPLIT_ORDER.map((s) => {
                      const v = data.cost_split[s.key] ?? 0;
                      return (
                        <span
                          key={s.key}
                          className="flex items-center gap-1.5 text-[11px] text-zinc-400"
                        >
                          <span
                            className={cn("h-2 w-2 rounded-[2px]", s.color)}
                          />
                          {s.label}
                          <span className="font-mono text-muted-foreground">
                            $<CountNum value={v} format={(x) => x.toFixed(2)} />
                          </span>
                        </span>
                      );
                    })}
                  </div>
                </>
              )}
            </section>

            {/* totals */}
            <section className="space-y-3">
              <SectionTitle>Totals</SectionTitle>
              <div className="grid grid-cols-4 gap-2 text-center">
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
                    className="rounded-lg border border-white/[0.08] bg-white/[0.02] py-3"
                  >
                    <p className="font-mono text-sm text-foreground">{node}</p>
                    <p className="mt-1 text-[10px] uppercase tracking-widest text-muted-foreground">
                      {label}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </aside>
    </div>
  );
}
