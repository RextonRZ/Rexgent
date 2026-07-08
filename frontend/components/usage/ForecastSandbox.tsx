"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";
import { useReducedMotion } from "@/hooks/useReducedMotion";
import { fmtUsd } from "@/components/usage/usageCharts";
import type { UsageAnalytics } from "@/hooks/useUsageAnalytics";

/** ── the budget-runway planner ───────────────────────────────────────────
 * Hero = runway: how long the remaining budget lasts at the chosen pace.
 * Three levers (pace, video quality, budget) recompute everything live.
 * Numbers are simple averages over this range's real spend, clamped so a
 * burst day can't produce nonsense — and the math is never narrated.
 */

// real per-second video rates — the quality lever maps to actual routing
const RATE = { economy: 0.108, balanced: 0.129, premium: 0.15 };
type Tier = keyof typeof RATE;

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
    // which tier the user's ACTUAL mix is closest to
    const myTier: Tier = wr > 0.66 ? "premium" : wr < 0.33 ? "economy" : "balanced";
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
      const late = active.slice(-half).reduce((s, d) => s + d.usd, 0) / half;
      if (early > 0) {
        const r = late / early;
        direction = r > 1.15 ? "accelerating" : r < 0.85 ? "slowing" : "stable";
      }
    }
    return { costPerEpisode, videoShare, blendedRate, myTier, pace, direction };
  }, [data]);

  // ── the levers ──
  const [pace, setPace] = useState(base.pace);
  const [tier, setTier] = useState<Tier>(base.myTier);
  const [budget, setBudget] = useState(10);
  const [editingBudget, setEditingBudget] = useState(false);
  useEffect(() => setPace(base.pace), [base.pace]);
  useEffect(() => setTier(base.myTier), [base.myTier]);

  const costFor = (t: Tier) => {
    const video = base.costPerEpisode * base.videoShare;
    const rest = base.costPerEpisode - video;
    return Math.max(
      0.05,
      rest + video * (RATE[t] / (base.blendedRate || RATE.economy))
    );
  };

  const costEp = costFor(tier);
  const weeklySpend = pace * costEp;
  const runwayEps = budget / costEp;
  const runwayWeeks = Math.min(MAX_WEEKS * 4, runwayEps / Math.max(pace, 0.01));
  const runOut = new Date(Date.now() + runwayWeeks * 7 * MS_DAY);
  const beyondYear = runwayWeeks * 7 > 365;

  // "what changed" vs the fixed baseline: my tier, my pace, $10.
  // Pace never changes HOW MANY episodes the budget buys — only WHEN it runs
  // out — so the pill speaks in days when pace is the thing that moved.
  const baselineRunway = 10 / costFor(base.myTier);
  const baselineDays = (baselineRunway / Math.max(base.pace, 0.01)) * 7;
  const dirty =
    tier !== base.myTier || Math.abs(pace - base.pace) > 0.01 || budget !== 10;
  const deltaEps = runwayEps - baselineRunway;
  const deltaDays = Math.min(999, runwayWeeks * 7) - Math.min(999, baselineDays);

  const easedRunway = useEased(runwayEps, reduced);
  const easedWeekly = useEased(weeklySpend, reduced);
  const easedEp = useEased(costEp, reduced);

  // ── chart: cumulative history (solid) + projection (dashed) + cap ──
  const chart = useMemo(() => {
    let acc = 0;
    const hist = data.trend.map((d) => {
      acc += d.usd;
      return { date: d.date, spend: acc };
    });
    const spent = acc;
    const cap = spent + budget;
    const weeks = Math.min(MAX_WEEKS, Math.max(runwayWeeks * 1.2, 4));
    const steps = Math.ceil(weeks * 2); // half-week resolution
    const proj = Array.from({ length: steps + 1 }, (_, i) =>
      Math.min(cap * 1.12, spent + (i / 2) * weeklySpend)
    );
    const maxY = Math.max(cap * 1.06, spent, 0.01);
    return { hist, spent, cap, proj, weeks, maxY };
  }, [data.trend, budget, weeklySpend, runwayWeeks]);

  const W = 100;
  const H = 40;
  const histSpan = Math.max(1, chart.hist.length - 1);
  const HIST_W = 0.42; // history left, future right
  const xHist = (i: number) => (i / histSpan) * (W * HIST_W);
  const xProj = (w: number) =>
    W * HIST_W + (w / Math.max(chart.weeks, 0.01)) * (W * (1 - HIST_W));
  const yOf = (v: number) => H - 5 - (v / chart.maxY) * (H - 12);

  const histPath = chart.hist
    .map(
      (p, i) => `${i === 0 ? "M" : "L"} ${xHist(i).toFixed(1)} ${yOf(p.spend).toFixed(1)}`
    )
    .join(" ");
  const projPath = chart.proj
    .map(
      (v, i) =>
        `${i === 0 ? "M" : "L"} ${xProj(i / 2).toFixed(1)} ${yOf(v).toFixed(1)}`
    )
    .join(" ");
  const crossW = Math.min(chart.weeks, runwayWeeks);

  // ── ONE way to explore the future: hover the chart (day resolution) ──
  const [hover, setHover] = useState<{
    xPct: number;
    date: Date;
    spend: number;
    eps: number | null; // null over history (episodes made only projects forward)
    daily?: number; // predicted spend on that single day
    runOut?: boolean; // hovering THE run-out point
  } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const onMove = (clientX: number) => {
    const el = svgRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const x = ((clientX - r.left) / r.width) * W;
    if (x <= W * HIST_W && chart.hist.length > 0) {
      const i = Math.round((x / (W * HIST_W)) * histSpan);
      const p = chart.hist[Math.min(histSpan, Math.max(0, i))];
      setHover({
        xPct: (xHist(Math.min(histSpan, Math.max(0, i))) / W) * 100,
        date: new Date(p.date),
        spend: p.spend,
        eps: null,
      });
    } else {
      const rawW = Math.min(
        chart.weeks,
        Math.max(0, ((x - W * HIST_W) / (W * (1 - HIST_W))) * chart.weeks)
      );
      // snap to whole days; the run-out point is magnetic (±1 day pulls
      // onto the EXACT crossing, not a rounded day — so crosshair, marker
      // and drop line always align)
      const day = Math.round(rawW * 7);
      const onRunOut =
        runwayWeeks <= chart.weeks && Math.abs(day - runwayWeeks * 7) <= 1;
      const w = onRunOut ? crossW : day / 7;
      setHover({
        xPct: (xProj(w) / W) * 100,
        date: onRunOut ? runOut : new Date(Date.now() + day * MS_DAY),
        spend: Math.min(chart.cap, chart.spent + w * weeklySpend),
        eps: w * pace,
        daily: weeklySpend / 7,
        runOut: onRunOut,
      });
    }
  };

  const spentPct = Math.min(100, (chart.spent / chart.cap) * 100);

  const chipTitle =
    "your spending rhythm across this range — history, unaffected by the sliders";
  const trendChip =
    base.direction === "accelerating" ? (
      <span title={chipTitle} className="cursor-help rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-300">
        ▲ pace accelerating
      </span>
    ) : base.direction === "slowing" ? (
      <span title={chipTitle} className="cursor-help rounded-full bg-sky-500/10 px-2 py-0.5 text-[10px] text-sky-300">
        ▼ pace slowing
      </span>
    ) : (
      <span title={chipTitle} className="cursor-help rounded-full bg-ok/10 px-2 py-0.5 text-[10px] text-ok">
        pace stable
      </span>
    );

  return (
    <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-5">
      {/* ── runway hero ── */}
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1.5">
        <p className="text-2xl font-semibold tracking-tight">
          {beyondYear
            ? "99+"
            : Math.max(0, easedRunway).toFixed(easedRunway >= 10 ? 0 : 1)}
          <span className="text-base text-zinc-400"> more episodes</span>
        </p>
        <p className="text-sm text-zinc-400">
          your{" "}
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
          budget runs out {beyondYear ? "in a year+" : `~${fmtDate(runOut)}`}
        </p>
        {trendChip}
        {dirty && (
          <span
            key={`${pace}-${tier}-${budget}`}
            className={cn(
              "rounded-full px-2 py-0.5 text-[10px] motion-safe:animate-in motion-safe:fade-in-0",
              (Math.abs(deltaEps) >= 0.05 ? deltaEps >= 0 : deltaDays >= 0)
                ? "bg-ok/10 text-ok"
                : "bg-amber-500/10 text-amber-300"
            )}
          >
            {Math.abs(deltaEps) >= 0.05
              ? `${deltaEps >= 0 ? "+" : "−"}${Math.abs(deltaEps).toFixed(1)} episodes vs your current`
              : `${deltaDays >= 0 ? "+" : "−"}${Math.abs(Math.round(deltaDays))} days of runway vs your current`}
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
                setTier(base.myTier);
                setBudget(10);
              }}
              className="flex items-center gap-1 text-[11px] text-zinc-500 hover:text-zinc-300"
            >
              <RotateCcw className="size-3" /> my actual pace
            </button>
          )}
        </span>
      </div>

      {/* runway bar: spent solid, the budget ghosted on top of it */}
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
      <div className="mt-1.5 flex justify-between text-[10px] text-zinc-600">
        <span>{fmtUsd(chart.spent)} spent so far</span>
        <span>
          + ${budget} budget · runs out {beyondYear ? "a year+" : `~${fmtDate(runOut)}`}
        </span>
      </div>

      {/* ── levers ── */}
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <div>
          <div className="flex items-baseline justify-between">
            <label htmlFor="pace" className="text-[10px] uppercase tracking-widest text-zinc-500">
              Pace
            </label>
            <span className="text-[11px] tabular-nums text-zinc-300">
              {pace.toFixed(pace >= 3 ? 0 : 1)} episodes / week
            </span>
          </div>
          <div className="relative mt-2">
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
            <span
              title="your current pace"
              className="absolute top-0 h-full w-[3px] cursor-help rounded-full bg-ok/80"
              style={{ left: `${((base.pace - 0.25) / 9.75) * 100}%` }}
            />
          </div>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-widest text-zinc-500">
            Video quality
          </p>
          <div className="mt-2 flex items-center gap-2.5">
          <div className="flex w-fit gap-0.5 rounded-lg border hairline bg-black/20 p-0.5">
            {(["economy", "balanced", "premium"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTier(t)}
                aria-pressed={tier === t}
                className={cn(
                  "relative rounded-md px-3 py-1 text-[11px] transition-colors motion-reduce:transition-none",
                  tier === t
                    ? "bg-primary/20 text-primary"
                    : "text-zinc-500 hover:text-zinc-300"
                )}
              >
                {t}
                {base.myTier === t && (
                  <span
                    title="you’re here"
                    className="absolute -top-0.5 right-1 h-1 w-1 rounded-full bg-ok"
                  />
                )}
              </button>
            ))}
          </div>
          <span className="flex items-center gap-1.5 text-[10px] text-zinc-500">
            <span className="h-1.5 w-1.5 rounded-full bg-ok" />
            you&apos;re here
          </span>
          </div>
        </div>
      </div>

      {/* ── stat cards, same rhythm as the money section ── */}
      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        {[
          {
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
            label: "Next 7 days",
            value: `≈ ${fmtUsd(easedWeekly)}`,
            sub: `at ${pace.toFixed(pace >= 3 ? 0 : 1)} episodes / week`,
          },
          {
            label: "Episodes per $10",
            value: `≈ ${(10 / costEp).toFixed(1)}`,
            sub: tier === base.myTier ? "on your current mix" : `on ${tier}`,
          },
        ].map((c) => (
          <div
            key={c.label}
            className="rounded-xl border border-white/[0.08] bg-white/[0.02] px-4 py-3"
          >
            <p className="text-[10px] uppercase tracking-widest text-zinc-500">
              {c.label}
            </p>
            <p className="mt-1 text-lg font-semibold tabular-nums">{c.value}</p>
            <p className="mt-0.5 text-[10px] text-zinc-500">{c.sub}</p>
          </div>
        ))}
      </div>

      {/* ── projection chart: history solid, projection dashed, one cap line,
       * one run-out marker. Hover anywhere for the readout. ── */}
      <div className="relative mt-5 pb-4">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className="h-32 w-full"
          preserveAspectRatio="none"
          onPointerMove={(e) => onMove(e.clientX)}
          onPointerLeave={() => setHover(null)}
        >
          {/* baseline */}
          <line
            x1={0}
            x2={W}
            y1={H - 5}
            y2={H - 5}
            stroke="rgba(255,255,255,0.06)"
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
          />
          <defs>
            {/* same finish as the Trend chart's area fill */}
            <linearGradient id="runwayFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.25} />
              <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          {/* budget cap: thin, muted, SOLID — never confusable with the
              dashed projection */}
          <line
            x1={0}
            x2={W}
            y1={yOf(chart.cap)}
            y2={yOf(chart.cap)}
            stroke="rgba(161,161,170,0.30)"
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
          />
          {/* history: gradient wash under a solid line */}
          {chart.hist.length > 1 && (
            <path
              d={`${histPath} L ${(W * HIST_W).toFixed(1)} ${H - 5} L 0 ${H - 5} Z`}
              fill="url(#runwayFill)"
            />
          )}
          <path
            d={histPath}
            fill="none"
            stroke="#8b5cf6"
            strokeWidth="1.5"
            vectorEffect="non-scaling-stroke"
          />
          {/* projection: clearly visible violet dashes */}
          <path
            d={projPath}
            fill="none"
            stroke="#a78bfa"
            strokeWidth="1.8"
            strokeDasharray="4 3"
            vectorEffect="non-scaling-stroke"
          />
          {/* run-out annotation, the classic way: a dashed drop line from the
              crossing down to the axis, a crisp dot on the intersection */}
          {runwayWeeks <= chart.weeks && (
            <>
              <line
                x1={xProj(crossW)}
                x2={xProj(crossW)}
                y1={yOf(chart.cap)}
                y2={H - 5}
                stroke="rgba(196,181,253,0.4)"
                strokeWidth="1"
                strokeDasharray="2 2"
                vectorEffect="non-scaling-stroke"
              />
              <circle
                cx={xProj(crossW)}
                cy={yOf(chart.cap)}
                r="2"
                fill="#c4b5fd"
                stroke="#12101c"
                strokeWidth="1"
              />
            </>
          )}
          {/* hover crosshair */}
          {hover && (
            <line
              x1={(hover.xPct / 100) * W}
              x2={(hover.xPct / 100) * W}
              y1={0}
              y2={H}
              stroke={hover.runOut ? "rgba(251,191,36,0.5)" : "rgba(167,139,250,0.35)"}
              strokeWidth="1"
              vectorEffect="non-scaling-stroke"
            />
          )}
        </svg>

        {/* labels: cap ABOVE the line at the right edge, run-out BELOW the
            marker's leader — clamped so their boxes can never meet */}
        <span
          className="pointer-events-none absolute right-1 whitespace-nowrap text-[9px] leading-none text-zinc-500"
          style={{
            top: `calc(${(yOf(chart.cap) / H) * 100}% - 11px)`,
          }}
        >
          budget cap {fmtUsd(chart.cap)}
        </span>
        {runwayWeeks <= chart.weeks && !beyondYear && (
          <span
            className="pointer-events-none absolute bottom-0 whitespace-nowrap text-[9px] font-medium leading-none text-violet-300"
            style={{
              left: `${Math.min(84, Math.max(8, (xProj(crossW) / W) * 100))}%`,
              transform: "translateX(-50%) translateY(120%)",
            }}
          >
            runs out ~{fmtDate(runOut)}
          </span>
        )}

        {/* dark app-native tooltip, same chrome as the Trend chart */}
        {hover && (
          <div
            className={cn(
              "pointer-events-none absolute -top-2 z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-md border px-2.5 py-1.5 shadow-lg",
              hover.runOut
                ? "border-amber-400/40 bg-[#1c1420]"
                : "border-white/10 bg-[#161122]"
            )}
            style={{ left: `${hover.xPct}%` }}
          >
            {hover.runOut ? (
              <>
                <p className="text-[10px] font-semibold text-amber-300">
                  ⚠ budget runs out here
                </p>
                <p className="text-[10px] tabular-nums text-zinc-400">
                  cap {fmtUsd(chart.cap)} reached · {hover.eps?.toFixed(1)} episodes made
                </p>
              </>
            ) : (
              <>
                <p className="text-[10px] text-zinc-200">{fmtDate(hover.date)}</p>
                <p className="text-[10px] tabular-nums text-zinc-400">
                  {fmtUsd(hover.spend)} spent
                  {hover.eps != null && ` · ${hover.eps.toFixed(1)} episodes made`}
                </p>
                {hover.eps != null && hover.daily != null && (
                  <p className="text-[10px] tabular-nums text-zinc-500">
                    ≈ {fmtUsd(hover.daily)} predicted that day
                  </p>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
