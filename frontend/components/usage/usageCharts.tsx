"use client";

import { useState } from "react";
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

/** ── chart primitives for the usage dashboard ────────────────────────────
 * Colors are validator-checked against the card surface (#12101c):
 * - the LLM tier split wears an ORDINAL violet ramp (light = cheap tier,
 *   dark = premium) — the routing story reads straight off the lightness;
 * - nominal magnitude bars (categories, dramas) wear one hue, slot-1 violet;
 * - marks stay thin, gaps do the separating, text wears text tokens.
 */

export const TIER_RAMP = ["#ddd6fe", "#a78bfa", "#8b5cf6", "#7c3aed", "#5b21b6"];
export const BAR_HUE = "#8b5cf6";

export const fmtTokens = (n: number) =>
  n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 1_000 ? `${Math.round(n / 1_000)}K` : String(n);

export const fmtUsd = (n: number) =>
  n >= 1 ? `$${n.toFixed(2)}` : n > 0 ? `$${n.toFixed(3)}` : "$0";

export const fmtPct = (p: number) => `${Math.round(p * 100)}%`;

export interface TierSegment {
  key: string;
  label: string;
  role: string;
  value: number;
  usd: number;
}

/** Horizontal 100% stacked bar: the five LLM tiers, cheap → premium. */
export function TierSplitBar({ segments }: { segments: TierSegment[] }) {
  const [hover, setHover] = useState<string | null>(null);
  const total = segments.reduce((s, x) => s + x.value, 0);
  if (!total) {
    return <p className="text-xs text-zinc-500">No language model usage in this range.</p>;
  }
  const dimmed = (key: string) => hover !== null && hover !== key;
  return (
    <div>
      <div className="flex h-9 w-full gap-[2px] overflow-hidden rounded-lg">
        {segments.map((s, i) =>
          s.value <= 0 ? null : (
            <div
              key={s.key}
              onMouseEnter={() => setHover(s.key)}
              onMouseLeave={() => setHover(null)}
              className="group relative flex items-center justify-center transition-opacity duration-150 motion-reduce:transition-none"
              style={{
                width: `${(s.value / total) * 100}%`,
                background: TIER_RAMP[i],
                opacity: dimmed(s.key) ? 0.3 : 1,
                minWidth: 3,
              }}
            >
              {s.value / total >= 0.12 && (
                <span
                  className="pointer-events-none truncate px-1 font-mono text-[10px] font-medium"
                  style={{ color: i < 2 ? "#1c1633" : "#f4f1ff" }}
                >
                  {fmtPct(s.value / total)}
                </span>
              )}
              {/* tooltip: exact value + share */}
              <div className="pointer-events-none absolute -top-1 left-1/2 z-10 hidden -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-lg border border-white/10 bg-[#181327] px-2.5 py-1.5 text-left shadow-xl group-hover:block">
                <p className="font-mono text-[10px] text-zinc-200">{s.label}</p>
                <p className="text-[10px] text-zinc-400">{s.role}</p>
                <p className="text-[10px] tabular-nums text-zinc-300">
                  {fmtTokens(s.value)} tokens · {fmtPct(s.value / total)} · {fmtUsd(s.usd)}
                </p>
              </div>
            </div>
          )
        )}
      </div>
      {/* legend: identity never rides on color alone */}
      <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1.5">
        {segments.map((s, i) => (
          <button
            key={s.key}
            onMouseEnter={() => setHover(s.key)}
            onMouseLeave={() => setHover(null)}
            className="flex items-center gap-1.5 text-left transition-opacity duration-150 motion-reduce:transition-none"
            style={{ opacity: dimmed(s.key) ? 0.4 : 1 }}
          >
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ background: TIER_RAMP[i] }}
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
}

/** Nominal magnitude rows: one series, one hue, values right-aligned. */
export function RankedBars({ rows }: { rows: RankedRow[] }) {
  const max = Math.max(...rows.map((r) => r.value), 0);
  if (!rows.length || max <= 0) {
    return <p className="text-xs text-zinc-500">Nothing in this range.</p>;
  }
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.label} className="group" title={`${r.label}: ${r.display}`}>
          <div className="mb-1 flex items-baseline justify-between gap-3">
            <span className="min-w-0 truncate text-xs text-zinc-300">{r.label}</span>
            <span className="shrink-0 text-right text-xs tabular-nums text-zinc-400">
              {r.display}
              {r.sub && <span className="ml-2 text-zinc-600">{r.sub}</span>}
            </span>
          </div>
          <div className="h-2 w-full rounded-full bg-white/[0.04]">
            <div
              className="h-2 rounded-full transition-opacity duration-150 group-hover:opacity-80 motion-reduce:transition-none"
              style={{ width: `${(r.value / max) * 100}%`, background: BAR_HUE, minWidth: 2 }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

const tooltipStyle = {
  background: "#181327",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 8,
  fontSize: 11,
  color: "#d4d4d8",
};

/** Spend + volume over time. Two panels, one x-axis notion — never dual-axis. */
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
  const short = (d: string) => d.slice(5); // MM-DD
  return (
    <div className="space-y-1">
      <p className="text-[10px] text-zinc-500">Spend per day (USD)</p>
      <ResponsiveContainer width="100%" height={160}>
        <AreaChart data={data} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
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
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v) => [fmtUsd(Number(v)), "spend"]}
            labelFormatter={(l) => String(l)}
          />
          <Area
            type="monotone"
            dataKey="usd"
            stroke={BAR_HUE}
            strokeWidth={2}
            fill={BAR_HUE}
            fillOpacity={0.1}
            isAnimationActive={!reduced}
            dot={false}
            activeDot={{ r: 4, stroke: "#12101c", strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
      <p className="pt-2 text-[10px] text-zinc-500">Clips rendered per day</p>
      <ResponsiveContainer width="100%" height={72}>
        <BarChart data={data} margin={{ top: 2, right: 8, left: -18, bottom: 0 }}>
          <XAxis dataKey="date" hide />
          <YAxis
            tick={{ fill: "#71717a", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            allowDecimals={false}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v) => [String(v), "clips"]}
            labelFormatter={(l) => String(l)}
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
