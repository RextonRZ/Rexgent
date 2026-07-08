"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";
import { useReducedMotion } from "@/hooks/useReducedMotion";
import { fmtUsd } from "@/components/usage/usageCharts";
import type { UsageAnalytics } from "@/hooks/useUsageAnalytics";

/** ── the budget-planning sandbox ─────────────────────────────────────────
 * Hero = runway: how long the budget lasts at the chosen pace. Every control
 * (pace slider, tier toggle, budget input, future scrubber) recomputes the
 * whole section live. Numbers come from simple averages over this range's
 * real spend — clamped and smoothed so one burst day can't produce nonsense.
 * The math is deliberately never narrated to the user.
 */

// real per-second video rates — the tier lever maps to actual routing
const RATE = { economy: 0.108, balanced: 0.129, premium: 0.15 };
type Tier = "actual" | keyof typeof RATE;

const MS_DAY = 86_400_000;
const MAX_WEEKS = 26;

/** Eases a displayed number toward its target in ~200ms. */
function useEased(target: number, reduced: boolean): number {
  const [shown, setShown] = useState(target);
  const raf = useRef(0);
  useEffect(() => {
    if (reduced) {
      setShown(target);
      return;
    }
    const from = shown;
    const t0 = performance.now();
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / 200);
      setShown(from + (target - from) * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, reduced]);
  return shown;
}

const fmtDate = (d: Date) =>
  d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });

export function ForecastSandbox({ data }: { data: UsageAnalytics }) {
  const reduced = useReducedMotion();

  // ── baseline from real usage (rolling, clamped) ──
  const base = useMemo(() => {
    const totalUsd = Object.values(data.categories).reduce((s, c) => s + c.usd, 0);
    const produced = data.dramas.filter((d) => d.clips > 0);
    const costPerEpisode = Math.max(
      0.05,
      produced.length ? totalUsd / produced.length : totalUsd || 1.5
    );
    const videoShare =
      totalUsd > 0 ? (data.categories["video"]?.usd ?? 0) / totalUsd : 0.7;
    const wan = data.reliability.by_tier["wan"]?.clips ?? 0;
    const hh = data.reliability.by_tier["happyhorse"]?.clips ?? 0;
    const wr = wan + hh > 0 ? wan / (wan + hh) : 0;
    const blendedRate = wr * RATE.premium + (1 - wr) * RATE.economy;
    const spanDays = Math.max(1, data.trend.length);
    const pace = Math.min(
      10,
      Math.max(0.25, produced.length ? (produced.length / spanDays) * 7 : 1)
    );
    // pace direction: rolling average of recent ACTIVE days vs earlier ones
    const active = data.trend.filter((d) => d.usd > 0);
    let direction: "accelerating" | "stable" | "slowing" = "stable";
    if (active.length >= 4) {
      const half = Math.floor(active.length / 2);
      const early = active.slice(0, half).reduce((s, d) => s + d.usd, 0) / half;
      const late =
        active.slice(-half).reduce((s, d) => s + d.usd, 0) / half;
      if (early > 0) {
        const r = late / early;
        direction = r > 1.15 ? "accelerating" : r < 0.85 ? "slowing" : "stable";
      }
    }
    return { totalUsd, costPerEpisode, videoShare, blendedRate, pace, direction };
  }, [data]);

  // ── the levers ──
  const [pace, setPace] = useState(base.pace);
  const [tier, setTier] = useState<Tier>("actual");
  const [budget, setBudget] = useState(10);
  const [editingBudget, setEditingBudget] = useState(false);
  const [scrubWeeks, setScrubWeeks] = useState<number | null>(null);
  const [hoverCard, setHoverCard] = useState<"episode" | "week" | "ten" | null>(null);
  useEffect(() => setPace(base.pace), [base.pace]);

  const costFor = (t: Tier) => {
    const rate = t === "actual" ? base.blendedRate : RATE[t];
    const video = base.costPerEpisode * base.videoShare;
    const rest = base.costPerEpisode - video;
    return Math.max(0.05, rest + video * (rate / (base.blendedRate || RATE.economy)));
  };

  const costEp = costFor(tier);
  const weeklySpend = pace * costEp;
  const runwayEps = budget / costEp;
  const runwayWeeks = Math.min(MAX_WEEKS * 4, runwayEps / Math.max(pace, 0.01));
  const runOut = new Date(Date.now() + runwayWeeks * 7 * MS_DAY);
  const beyondYear = runwayWeeks * 7 > 365;

  // "what changed" vs the fixed baseline: my actual mix, my pace, $10
  const baselineRunway = 10 / costFor("actual");
  const dirty = tier !== "actual" || Math.abs(pace - base.pace) > 0.01 || budget !== 10;
  const deltaEps = runwayEps - baselineRunway;

  const easedRunway = useEased(runwayEps, reduced);
  const easedWeekly = useEased(weeklySpend, reduced);
  const easedEp = useEased(costEp, reduced);

  // ── chart geometry: cumulative history + projected line + cap ──
  const chart = useMemo(() => {
    let acc = 0;
    const hist = data.trend.map((d) => {
      acc += d.usd;
      return acc;
    });
    const spent = acc;
    const cap = spent + budget;
    const weeks = Math.min(MAX_WEEKS, Math.max(runwayWeeks * 1.2, 4));
    const steps = Math.ceil(weeks);
    const proj = Array.from({ length: steps + 1 }, (_, w) =>
      Math.min(cap * 1.15, spent + w * weeklySpend)
    );
    const maxY = Math.max(cap * 1.05, proj[proj.length - 1], spent, 0.01);
    return { hist, spent, cap, proj, weeks, maxY };
  }, [data.trend, budget, weeklySpend, runwayWeeks]);

  const W = 100;
  const H = 40;
  const histSpan = Math.max(1, chart.hist.length - 1);
  // history occupies the left 40%, the future the right 60%
  const xHist = (i: number) => (i / histSpan) * (W * 0.4);
  const xProj = (w: number) => W * 0.4 + (w / Math.max(chart.weeks, 1)) * (W * 0.6);
  const yOf = (v: number) => H - 4 - (v / chart.maxY) * (H - 10);
  const crossX = xProj(Math.min(chart.weeks, runwayWeeks));

  const histPath = chart.hist
    .map((v, i) => `${i === 0 ? "M" : "L"} ${xHist(i).toFixed(1)} ${yOf(v).toFixed(1)}`)
    .join(" ");
  const projPath = chart.proj
    .map((v, w) => `${w === 0 ? "M" : "L"} ${xProj(w).toFixed(1)} ${yOf(v).toFixed(1)}`)
    .join(" ");

  // scrubber: weeks into the future (defaults to the run-out point)
  const scrub = scrubWeeks ?? Math.min(chart.weeks, runwayWeeks);
  const scrubSpend = chart.spent + scrub * weeklySpend;
  const scrubEps = scrub * pace;
  const scrubDate = new Date(Date.now() + scrub * 7 * MS_DAY);

  const svgRef = useRef<SVGSVGElement>(null);
  const dragScrub = (clientX: number) => {
    const el = svgRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const x = ((clientX - r.left) / r.width) * W;
    const w = ((x - W * 0.4) / (W * 0.6)) * chart.weeks;
    setScrubWeeks(Math.min(chart.weeks, Math.max(0, w)));
  };

  const segBtn = (t: Tier, label: string) => (
    <button
      key={t}
      onClick={() => setTier(t)}
      aria-pressed={tier === t}
      className={cn(
        "rounded-md px-2.5 py-1 text-[11px] transition-colors motion-reduce:transition-none",
        tier === t
          ? "bg-primary/20 text-primary"
          : "text-zinc-500 hover:text-zinc-300"
      )}
    >
      {label}
    </button>
  );

  const trendChip =
    base.direction === "accelerating" ? (
      <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-300">
        ▲ accelerating
      </span>
    ) : base.direction === "slowing" ? (
      <span className="rounded-full bg-sky-500/10 px-2 py-0.5 text-[10px] text-sky-300">
        ▼ slowing
      </span>
    ) : (
      <span className="rounded-full bg-ok/10 px-2 py-0.5 text-[10px] text-ok">
        stable
      </span>
    );

  const spentPct = Math.min(100, (chart.spent / chart.cap) * 100);

  return (
    <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-5">
      {/* ── 1 · runway hero ── */}
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <p className="text-2xl font-semibold tracking-tight">
          {beyondYear ? "99+" : Math.max(0, easedRunway).toFixed(easedRunway >= 10 ? 0 : 1)}
          <span className="text-base text-zinc-400"> more episodes</span>
        </p>
        <p className="text-sm text-zinc-400">
          at this pace, your{" "}
          {editingBudget ? (
            <input
              autoFocus
              type="number"
              min={1}
              max={500}
              defaultValue={budget}
              onBlur={(e) => {
                setBudget(Math.max(1, Math.min(500, Number(e.target.value) || budget)));
                setEditingBudget(false);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              }}
              className="w-16 rounded border border-primary/40 bg-transparent px-1 text-center text-primary outline-none"
            />
          ) : (
            <button
              onClick={() => setEditingBudget(true)}
              title="Click to edit the budget"
              className="rounded px-0.5 font-medium text-primary underline decoration-dotted underline-offset-2 hover:bg-primary/10"
            >
              ${budget}
            </button>
          )}{" "}
          runs out {beyondYear ? "in a year+" : `~${fmtDate(runOut)}`}
        </p>
        {trendChip}
        {dirty && (
          <span
            key={`${pace}-${tier}-${budget}`}
            className={cn(
              "rounded-full px-2 py-0.5 text-[10px] motion-safe:animate-in motion-safe:fade-in-0",
              deltaEps >= 0
                ? "bg-ok/10 text-ok"
                : "bg-amber-500/10 text-amber-300"
            )}
          >
            {deltaEps >= 0 ? "+" : "−"}
            {Math.abs(deltaEps).toFixed(1)} episodes vs my mix
          </span>
        )}
        <span className="ml-auto flex items-center gap-2">
          <button
            onClick={() => setBudget((b) => Math.min(500, b + 10))}
            className="rounded-full border border-primary/30 bg-primary/10 px-2.5 py-0.5 text-[11px] text-primary transition-colors hover:bg-primary/20 motion-reduce:transition-none"
          >
            +$10 voucher
          </button>
          {dirty && (
            <button
              onClick={() => {
                setPace(base.pace);
                setTier("actual");
                setBudget(10);
                setScrubWeeks(null);
              }}
              className="flex items-center gap-1 text-[11px] text-zinc-500 hover:text-zinc-300"
            >
              <RotateCcw className="size-3" /> my actual pace
            </button>
          )}
        </span>
      </div>

      {/* runway bar: spent solid → remaining ghosted, run-out marked */}
      <div className="relative mt-3 h-3 w-full overflow-hidden rounded-full bg-white/[0.04]">
        <div
          className="absolute inset-y-0 left-0 rounded-l-full bg-violet-500 transition-[width] duration-200 motion-reduce:transition-none"
          style={{ width: `${spentPct}%` }}
        />
        <div
          className="absolute inset-y-0 rounded-r-full transition-[left,width] duration-200 motion-reduce:transition-none"
          style={{
            left: `${spentPct}%`,
            width: `${100 - spentPct}%`,
            background:
              "repeating-linear-gradient(45deg, rgba(139,92,246,0.35) 0 4px, rgba(139,92,246,0.12) 4px 8px)",
          }}
        />
        <span
          className="absolute inset-y-0 w-px bg-white/70"
          style={{ left: `${spentPct}%` }}
          title="now"
        />
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-zinc-600">
        <span>{fmtUsd(chart.spent)} spent</span>
        <span>
          runs out {beyondYear ? "a year+" : fmtDate(runOut)} · cap {fmtUsd(chart.cap)}
        </span>
      </div>

      {/* ── 2 · levers ── */}
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <div>
          <div className="flex items-baseline justify-between">
            <label htmlFor="pace" className="text-[11px] text-zinc-500">
              Pace
            </label>
            <span className="text-[11px] tabular-nums text-zinc-300">
              {pace.toFixed(pace >= 3 ? 0 : 1)} episodes / week
            </span>
          </div>
          <div className="relative mt-1">
            <input
              id="pace"
              type="range"
              min={0.25}
              max={10}
              step={0.25}
              value={pace}
              onChange={(e) => setPace(Number(e.target.value))}
              className="w-full accent-violet-500"
            />
            {/* your current pace, marked on the track */}
            <span
              aria-hidden
              title="your current pace"
              className="pointer-events-none absolute top-0 h-full w-px bg-ok/70"
              style={{ left: `${((base.pace - 0.25) / 9.75) * 100}%` }}
            />
          </div>
        </div>
        <div>
          <p className="text-[11px] text-zinc-500">Video quality</p>
          <div className="mt-1 flex w-fit gap-0.5 rounded-lg border hairline bg-black/20 p-0.5">
            {segBtn("actual", "my mix")}
            {segBtn("economy", "economy")}
            {segBtn("balanced", "balanced")}
            {segBtn("premium", "premium")}
          </div>
        </div>
      </div>

      {/* ── 3 · stat cards, live + chart-linked ── */}
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {(
          [
            {
              key: "episode" as const,
              label: "Next episode",
              value: `≈ ${fmtUsd(easedEp)}`,
              sub:
                Math.abs(costEp - base.costPerEpisode) < base.costPerEpisode * 0.05
                  ? "≈ your average"
                  : `${costEp > base.costPerEpisode ? "▲" : "▼"} ${Math.round(
                      (Math.abs(costEp - base.costPerEpisode) / base.costPerEpisode) * 100
                    )}% vs your average`,
            },
            {
              key: "week" as const,
              label: "Next 7 days",
              value: `≈ ${fmtUsd(easedWeekly)}`,
              sub: `${pace.toFixed(1)} ep/wk × ${fmtUsd(costEp)}`,
            },
            {
              key: "ten" as const,
              label: "Episodes per $10",
              value: `≈ ${(10 / costEp).toFixed(1)}`,
              sub: tier === "actual" ? "on my mix" : `on ${tier}`,
            },
          ] as const
        ).map((c) => (
          <div
            key={c.key}
            onMouseEnter={() => setHoverCard(c.key)}
            onMouseLeave={() => setHoverCard(null)}
            className={cn(
              "rounded-lg border px-3 py-2.5 transition-colors duration-150 motion-reduce:transition-none",
              hoverCard === c.key
                ? "border-primary/40 bg-primary/[0.06]"
                : "border-white/[0.06] bg-white/[0.015]"
            )}
          >
            <p className="text-[10px] uppercase tracking-widest text-zinc-500">
              {c.label}
            </p>
            <p className="mt-0.5 text-lg font-semibold tabular-nums">{c.value}</p>
            <p className="text-[10px] text-zinc-500">{c.sub}</p>
          </div>
        ))}
      </div>

      {/* ── 4 · projection chart with cap line + draggable future target ── */}
      <div className="mt-4">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className="h-36 w-full cursor-crosshair touch-none"
          preserveAspectRatio="none"
          onPointerDown={(e) => {
            (e.target as Element).setPointerCapture?.(e.pointerId);
            dragScrub(e.clientX);
          }}
          onPointerMove={(e) => {
            if (e.buttons === 1) dragScrub(e.clientX);
          }}
        >
          {/* hovered card regions */}
          {hoverCard === "week" && (
            <rect
              x={xProj(0)}
              y={0}
              width={xProj(1) - xProj(0)}
              height={H}
              fill="rgba(139,92,246,0.10)"
            />
          )}
          {hoverCard === "episode" && (
            <rect
              x={xProj(0)}
              y={0}
              width={Math.max(1, xProj(1 / Math.max(pace, 0.01)) - xProj(0))}
              height={H}
              fill="rgba(139,92,246,0.10)"
            />
          )}
          {hoverCard === "ten" && (
            <rect
              x={0}
              y={yOf(Math.min(chart.maxY, chart.spent + 10))}
              width={W}
              height={Math.max(1, yOf(chart.spent) - yOf(chart.spent + 10))}
              fill="rgba(139,92,246,0.10)"
            />
          )}
          {/* budget cap */}
          <line
            x1={0}
            x2={W}
            y1={yOf(chart.cap)}
            y2={yOf(chart.cap)}
            stroke="rgba(251,191,36,0.45)"
            strokeWidth="1"
            strokeDasharray="1.5 2.5"
            vectorEffect="non-scaling-stroke"
          />
          {/* history + projection */}
          <path d={histPath} fill="none" stroke="#8b5cf6" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
          <path
            d={`M ${(W * 0.4).toFixed(1)} ${yOf(chart.spent).toFixed(1)} ${projPath.slice(projPath.indexOf("L"))}`}
            fill="none"
            stroke="#a78bfa"
            strokeWidth="1.5"
            strokeDasharray="3 3"
            vectorEffect="non-scaling-stroke"
          />
          {/* run-out crossing */}
          {runwayWeeks <= chart.weeks && (
            <circle cx={crossX} cy={yOf(chart.cap)} r="2" fill="#fbbf24" />
          )}
          {/* the draggable future target */}
          <line
            x1={xProj(scrub)}
            x2={xProj(scrub)}
            y1={0}
            y2={H}
            stroke="rgba(255,255,255,0.18)"
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
          />
          <circle
            cx={xProj(scrub)}
            cy={yOf(Math.min(scrubSpend, chart.maxY))}
            r="2.6"
            fill="#c4b5fd"
            stroke="#12101c"
            strokeWidth="1"
            className={cn(!reduced && "transition-[cx,cy] duration-100")}
          />
        </svg>
        <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
          <p className="text-[11px] tabular-nums text-zinc-400">
            by {fmtDate(scrubDate)}: ~{fmtUsd(scrubSpend)} spent ·{" "}
            {scrubEps.toFixed(1)} episodes made
          </p>
          <label className="flex items-center gap-2 text-[10px] text-zinc-600">
            scrub the future
            <input
              type="range"
              min={0}
              max={chart.weeks}
              step={0.25}
              value={scrub}
              onChange={(e) => setScrubWeeks(Number(e.target.value))}
              aria-label="Weeks into the future"
              className="w-28 accent-violet-500"
            />
          </label>
        </div>
      </div>
    </div>
  );
}
