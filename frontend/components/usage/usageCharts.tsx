"use client";

import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { cn } from "@/lib/utils";
import { useReducedMotion } from "@/hooks/useReducedMotion";

/** ── chart primitives for the usage dashboard ────────────────────────────
 * Colors are validator-checked against the card surface (#12101c):
 * - the LLM tier split wears an ORDINAL violet ramp (light = cheap tier,
 *   dark = premium) — the routing story reads straight off the lightness;
 * - nominal magnitude bars (categories, dramas) wear one hue, slot-1 violet;
 * - marks stay thin, gaps do the separating, text wears text tokens.
 * Tooltip chrome matches the Studio stats TIP style app-wide.
 */

export const TIER_RAMP = ["#ddd6fe", "#a78bfa", "#8b5cf6", "#7c3aed", "#5b21b6"];
export const BAR_HUE = "#8b5cf6";

/** Shared dark tooltip chrome — same as Studio stats. */
const TIP =
  "pointer-events-none whitespace-nowrap rounded-md border border-white/10 bg-[#161122] px-2.5 py-1.5 shadow-lg";

export const fmtTokens = (n: number) =>
  n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 1_000 ? `${Math.round(n / 1_000)}K` : String(n);

export const fmtUsd = (n: number) =>
  n >= 1 ? `$${n.toFixed(2)}` : n > 0 ? `$${n.toFixed(3)}` : "$0";

export const fmtPct = (p: number) => `${Math.round(p * 100)}%`;

/** Once-on-mount reveal: children scale in from the left (the "filling" read). */
function useMountReveal(reduced: boolean) {
  const [ready, setReady] = useState(reduced);
  useEffect(() => {
    if (reduced) return;
    const raf = requestAnimationFrame(() => setReady(true));
    return () => cancelAnimationFrame(raf);
  }, [reduced]);
  return ready;
}

export interface TierSegment {
  key: string;
  label: string;
  /** short in-bar name ("flash", "vl-plus") */
  short: string;
  role: string;
  value: number;
  usd: number;
  color: string;
  /** in-segment label ink, picked per fill luminance */
  ink: string;
}

/** The showpiece: a horizontal 100% stacked bar of the LLM tiers, cheap →
 * premium (plus a gray "other" tail), pill ends, inline "flash 20%" labels,
 * filling left→right on mount, cross-highlighted on hover. */
export function TierSplitBar({ segments }: { segments: TierSegment[] }) {
  const reduced = useReducedMotion();
  const ready = useMountReveal(reduced);
  const [hover, setHover] = useState<string | null>(null);
  const visible = segments.filter((s) => s.value > 0);
  const total = visible.reduce((s, x) => s + x.value, 0);
  if (!total) {
    return <p className="text-xs text-zinc-500">No language model usage in this range.</p>;
  }
  const dimmed = (key: string) => hover !== null && hover !== key;
  return (
    <div>
      <div
        className="flex h-[34px] w-full origin-left gap-[3px] overflow-visible transition-transform duration-700 ease-out motion-reduce:transition-none"
        style={{ transform: ready ? "scaleX(1)" : "scaleX(0)" }}
      >
        {visible.map((s, i) => {
          const share = s.value / total;
          return (
            <div
              key={s.key}
              onMouseEnter={() => setHover(s.key)}
              onMouseLeave={() => setHover(null)}
              className={cn(
                "group relative flex items-center justify-center rounded-[5px] transition-[opacity,transform] duration-150 motion-reduce:transition-none",
                i === 0 && "rounded-l-[17px]",
                i === visible.length - 1 && "rounded-r-[17px]",
                !dimmed(s.key) && hover === s.key && "motion-safe:-translate-y-[1px]"
              )}
              style={{
                width: `${share * 100}%`,
                background: s.color,
                opacity: dimmed(s.key) ? 0.25 : 1,
                minWidth: 5,
                boxShadow: hover === s.key ? `0 0 18px ${s.color}55` : undefined,
              }}
            >
              {share >= 0.1 && (
                <span
                  className="pointer-events-none truncate px-1.5 font-mono text-[10px] font-medium transition-opacity delay-500 duration-300 motion-reduce:transition-none"
                  style={{ color: s.ink, opacity: ready ? 1 : 0 }}
                >
                  {s.short} {fmtPct(share)}
                </span>
              )}
              {/* tooltip: model + role + exact tokens + share */}
              <div
                className={cn(
                  TIP,
                  "absolute -top-1.5 left-1/2 z-10 hidden -translate-x-1/2 -translate-y-full text-left group-hover:block"
                )}
              >
                <p className="font-mono text-[10px] text-zinc-200">{s.label}</p>
                <p className="text-[10px] text-zinc-500">{s.role}</p>
                <p className="text-[10px] tabular-nums text-zinc-300">
                  {fmtTokens(s.value)} tokens · {fmtPct(share)} · {fmtUsd(s.usd)}
                </p>
              </div>
            </div>
          );
        })}
      </div>
      {/* legend: every segment named, identity never rides on color alone */}
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
        {visible.map((s) => (
          <button
            key={s.key}
            onMouseEnter={() => setHover(s.key)}
            onMouseLeave={() => setHover(null)}
            className="flex items-center gap-1.5 text-left transition-opacity duration-150 motion-reduce:transition-none"
            style={{ opacity: dimmed(s.key) ? 0.35 : 1 }}
          >
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ background: s.color }}
            />
            <span className="font-mono text-[10px] text-zinc-300">{s.label}</span>
            <span className="text-[10px] text-zinc-500">{s.role}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export interface RankedRow {
  label: string;
  value: number;
  display: string;
  sub?: string;
  /** optional leading media (a drama's poster thumb) — the row becomes a
   * recognizable production, not just text */
  thumb?: React.ReactNode;
}

/** Nominal magnitude rows: one series, one hue. Hovering a row dims the
 * others and raises a tooltip with the exact value + share of total. */
export function RankedBars({ rows }: { rows: RankedRow[] }) {
  const reduced = useReducedMotion();
  const ready = useMountReveal(reduced);
  const [hover, setHover] = useState<string | null>(null);
  const max = Math.max(...rows.map((r) => r.value), 0);
  const total = rows.reduce((s, r) => s + r.value, 0);
  if (!rows.length || max <= 0) {
    return <p className="text-xs text-zinc-500">Nothing in this range.</p>;
  }
  return (
    <div className="space-y-2.5">
      {rows.map((r) => {
        const dim = hover !== null && hover !== r.label;
        return (
          <div
            key={r.label}
            onMouseEnter={() => setHover(r.label)}
            onMouseLeave={() => setHover(null)}
            className="relative flex items-center gap-2.5 transition-opacity duration-150 motion-reduce:transition-none"
            style={{ opacity: dim ? 0.4 : 1 }}
          >
            {r.thumb}
            <div className="min-w-0 flex-1">
              <div className="mb-1 flex items-baseline justify-between gap-3">
                <span className="min-w-0 truncate text-xs text-zinc-300">{r.label}</span>
                <span className="shrink-0 text-right text-xs tabular-nums text-zinc-400">
                  {r.display}
                  {r.sub && <span className="ml-2 text-zinc-600">{r.sub}</span>}
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-white/[0.04]">
                <div
                  className="h-2 rounded-full transition-[width] duration-700 ease-out motion-reduce:transition-none"
                  style={{
                    width: ready ? `${(r.value / max) * 100}%` : "0%",
                    background: BAR_HUE,
                    minWidth: ready ? 2 : 0,
                    boxShadow: hover === r.label ? `0 0 14px ${BAR_HUE}55` : undefined,
                  }}
                />
              </div>
            </div>
            {hover === r.label && total > 0 && (
              <div className={cn(TIP, "absolute -top-1 left-0 z-10 -translate-y-full")}>
                <p className="text-[10px] text-zinc-200">{r.label}</p>
                <p className="text-[10px] tabular-nums text-zinc-400">
                  {r.display} · {fmtPct(r.value / total)} of total
                </p>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

const tooltipStyle = {
  background: "#161122",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 8,
  fontSize: 11,
  color: "#d4d4d8",
  boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
};

const CHART_MARGIN = { top: 4, right: 8, left: -14, bottom: 0 };

/** Spend + volume over time. Two panels, one aligned x-axis, hover synced —
 * they read as one connected story. Never dual-axis. */
export function TrendChart({
  data,
  reduced,
}: {
  data: { date: string; usd: number; clips: number }[];
  reduced: boolean;
}) {
  if (data.length === 0) {
    return <p className="text-xs text-zinc-500">No activity in this range yet.</p>;
  }
  const short = (d: string) => d.slice(5);
  return (
    <div className="space-y-1">
      <p className="text-[10px] uppercase tracking-widest text-zinc-500">
        Spend per day
      </p>
      <ResponsiveContainer width="100%" height={160}>
        <AreaChart data={data} margin={CHART_MARGIN} syncId="usage-trend">
          <defs>
            <linearGradient id="spendFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={BAR_HUE} stopOpacity={0.28} />
              <stop offset="100%" stopColor={BAR_HUE} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
          <XAxis dataKey="date" hide />
          <YAxis
            tick={{ fill: "#71717a", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            width={44}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v) => [fmtUsd(Number(v)), "spend"]}
            labelFormatter={(l) => String(l)}
            cursor={{ stroke: "rgba(167,139,250,0.35)", strokeWidth: 1 }}
          />
          <Area
            type="monotone"
            dataKey="usd"
            stroke={BAR_HUE}
            strokeWidth={2}
            fill="url(#spendFill)"
            isAnimationActive={!reduced}
            dot={false}
            activeDot={{ r: 4, stroke: "#12101c", strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
      <p className="pt-2 text-[10px] uppercase tracking-widest text-zinc-500">
        Clips rendered per day
      </p>
      <ResponsiveContainer width="100%" height={88}>
        <BarChart data={data} margin={CHART_MARGIN} syncId="usage-trend">
          <XAxis
            dataKey="date"
            tickFormatter={short}
            tick={{ fill: "#71717a", fontSize: 10 }}
            axisLine={{ stroke: "rgba(255,255,255,0.08)" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "#71717a", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            allowDecimals={false}
            width={44}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v) => [String(v), "clips"]}
            labelFormatter={(l) => String(l)}
            cursor={{ fill: "rgba(167,139,250,0.08)" }}
          />
          <Bar
            dataKey="clips"
            fill={BAR_HUE}
            radius={[3, 3, 0, 0]}
            maxBarSize={14}
            isAnimationActive={!reduced}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
