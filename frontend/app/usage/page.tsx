"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { UserMenu } from "@/components/auth/UserMenu";
import { PageHeader } from "@/components/shared/PageHeader";
import { useReducedMotion } from "@/hooks/useReducedMotion";
import { useCountUp } from "@/hooks/useCountUp";
import {
  useUsageAnalytics,
  type UsageAnalytics,
  type UsageRange,
} from "@/hooks/useUsageAnalytics";
import {
  RankedBars,
  TierSplitBar,
  TrendChart,
  fmtPct,
  fmtTokens,
  fmtUsd,
  type TierSegment,
} from "@/components/usage/usageCharts";

/** Tier order is the story: cheap on the left, premium on the right, so the
 * light mass of the ramp IS the routing win. */
const TIER_ORDER = [
  { key: "qwen-flash", label: "qwen-flash", role: "cheap structured work" },
  { key: "qwen-plus", label: "qwen-plus", role: "judgment + chat" },
  { key: "qwen3-vl-plus", label: "qwen3-vl-plus", role: "continuity vision" },
  { key: "qwen-max", label: "qwen-max", role: "creative writing" },
  { key: "qwen-vl-max", label: "qwen-vl-max", role: "reference analysis" },
];

interface RosterModel {
  name: string;
  role: string;
}
const ROSTER: {
  group: string;
  unit: string;
  category: string | null; // categories key for subtotal (null = llm)
  models: RosterModel[];
}[] = [
  {
    group: "Language",
    unit: "token",
    category: null,
    models: [
      { name: "qwen-max", role: "Creative writing — script and shot direction" },
      { name: "qwen-plus", role: "Judgment — narrative judge, chat, relationships" },
      { name: "qwen-flash", role: "Structured work — parsing, extraction, wardrobe, titles" },
      { name: "qwen3-vl-plus", role: "Continuity vision — face and scene drift scoring" },
      { name: "qwen-vl-max", role: "Reference photo and appearance analysis" },
    ],
  },
  {
    group: "Image",
    unit: "image",
    category: "image",
    models: [
      { name: "wan2.6-t2i", role: "Reference plates — character, location, style" },
      { name: "qwen-image-edit-max", role: "Costume plates and frame edits" },
    ],
  },
  {
    group: "Video",
    unit: "second",
    category: "video",
    models: [
      { name: "wan2.7-t2v / i2v", role: "Premium tier — the shots that matter" },
      { name: "happyhorse-1.1-t2v / i2v / r2v", role: "Economy tier — supporting shots" },
      { name: "happyhorse-1.0-video-edit", role: "Fix a take — the regen loop" },
    ],
  },
  {
    group: "Voice",
    unit: "character",
    category: "tts",
    models: [
      { name: "qwen3-tts-flash", role: "Preset voices" },
      { name: "qwen3-tts-vc-realtime", role: "Cloned voices" },
      { name: "qwen-voice-enrollment", role: "Clone enrollment" },
    ],
  },
];

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-xs font-medium uppercase tracking-widest text-zinc-500">
      {children}
    </h2>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border hairline bg-card px-4 py-3">
      <p className="text-[11px] text-zinc-500">{label}</p>
      <p className="mt-0.5 text-lg font-semibold">{value}</p>
      {hint && <p className="text-[10px] text-zinc-600">{hint}</p>}
    </div>
  );
}

type Health = "ok" | "warn" | "bad";
function HealthCard({
  label,
  value,
  health,
  note,
}: {
  label: string;
  value: string;
  health: Health | null;
  note?: string;
}) {
  const Icon =
    health === "ok" ? CheckCircle2 : health === "warn" ? AlertTriangle : XCircle;
  return (
    <div className="rounded-xl border hairline bg-card px-4 py-3">
      <p className="text-[11px] text-zinc-500">{label}</p>
      <p className="mt-0.5 flex items-center gap-2 text-lg font-semibold">
        {value}
        {health && (
          <Icon
            className={cn(
              "size-4",
              health === "ok" && "text-ok",
              health === "warn" && "text-warn",
              health === "bad" && "text-bad"
            )}
            aria-label={health === "ok" ? "healthy" : health === "warn" ? "watch" : "problem"}
          />
        )}
      </p>
      {note && <p className="mt-0.5 text-[10px] text-zinc-500">{note}</p>}
    </div>
  );
}

const RANGES: { key: UsageRange; label: string }[] = [
  { key: "7d", label: "7d" },
  { key: "30d", label: "30d" },
  { key: "all", label: "All" },
];

export default function UsagePage() {
  const reduced = useReducedMotion();
  const [range, setRange] = useState<UsageRange>("30d");
  const { data, isLoading } = useUsageAnalytics(range);

  return (
    <main className="min-h-screen">
      <header className="glass sticky top-0 z-40 border-b hairline">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-6">
          <Link
            href="/projects"
            className="flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/rexgent_wordmark.png" alt="Rexgent" className="h-4 w-auto" />
          </Link>
          <UserMenu />
        </div>
      </header>

      <div className="mx-auto max-w-5xl space-y-10 px-6 py-8">
        <PageHeader
          title="Usage & analytics"
          sub="13 Qwen Cloud models, routed by task. This page proves the routing works and shows where the money goes."
        >
          <div className="flex rounded-lg border hairline p-0.5" role="tablist" aria-label="Time range">
            {RANGES.map((r) => (
              <button
                key={r.key}
                role="tab"
                aria-selected={range === r.key}
                onClick={() => setRange(r.key)}
                className={cn(
                  "rounded-md px-3 py-1 text-xs transition-colors motion-reduce:transition-none",
                  range === r.key
                    ? "bg-primary/15 text-primary"
                    : "text-zinc-500 hover:text-zinc-300"
                )}
              >
                {r.label}
              </button>
            ))}
          </div>
        </PageHeader>

        {isLoading || !data ? (
          <p className="text-sm text-zinc-500">Reading the ledger…</p>
        ) : (
          <Dashboard data={data} reduced={reduced} />
        )}
      </div>
    </main>
  );
}

function Dashboard({ data, reduced }: { data: UsageAnalytics; reduced: boolean }) {
  const byModel = new Map(data.llm.by_model.map((r) => [r.model, r]));
  const segments: TierSegment[] = TIER_ORDER.map((t) => ({
    key: t.key,
    label: t.label,
    role: t.role,
    value: byModel.get(t.key)?.tokens ?? 0,
    usd: byModel.get(t.key)?.usd ?? 0,
  }));
  // models the router doesn't know still count as premium-side "other"
  const known = new Set(TIER_ORDER.map((t) => t.key));
  for (const r of data.llm.by_model) {
    if (!known.has(r.model)) {
      segments.push({ key: r.model, label: r.model, role: "other", value: r.tokens, usd: r.usd });
    }
  }

  const cheapPct = useCountUp(Math.round(data.llm.cheap_share * 100), reduced);
  const saved = useCountUp(data.llm.saved_usd, reduced);

  const cheapLeaders = segments
    .filter((s) => !["qwen-max", "qwen-vl-max"].includes(s.key) && s.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, 2)
    .map((s) => s.label);

  const cats = data.categories;
  const catRows = (
    [
      ["Video", "video", (q: number) => `${Math.round(q)}s of footage`],
      ["Language", "llm", (q: number) => `${fmtTokens(q)} tokens`],
      ["Image", "image", (q: number) => `${Math.round(q)} images`],
      ["Voice", "tts", (q: number) => `${fmtTokens(q)} characters`],
    ] as const
  )
    .filter(([, key]) => cats[key])
    .map(([label, key, subFn]) => ({
      label,
      value: cats[key].usd,
      display: fmtUsd(cats[key].usd),
      sub: subFn(cats[key].quantity),
    }))
    .sort((a, b) => b.value - a.value);

  const totalUsd = Object.values(cats).reduce((s, c) => s + c.usd, 0);
  const videoShare = cats["video"] && totalUsd > 0 ? cats["video"].usd / totalUsd : 0;

  const dramaRows = data.dramas.slice(0, 8).map((d) => ({
    label: d.title,
    value: d.usd,
    display: fmtUsd(d.usd),
    sub: d.usd_per_min != null ? `${fmtUsd(d.usd_per_min)}/min of film` : undefined,
  }));

  const finished = data.dramas.filter((d) => d.runtime_seconds);
  const totalMinutes =
    finished.reduce((s, d) => s + (d.runtime_seconds ?? 0), 0) / 60;
  const totalClips = data.dramas.reduce((s, d) => s + d.clips, 0);

  const rel = data.reliability;
  const wan = rel.by_tier["wan"];
  const hh = rel.by_tier["happyhorse"];
  const passHealth: Health | null =
    rel.continuity_pass_rate == null
      ? null
      : rel.continuity_pass_rate >= 0.8
        ? "ok"
        : rel.continuity_pass_rate >= 0.6
          ? "warn"
          : "bad";
  const retryHealth = (r?: { retry_rate: number }): Health | null =>
    !r ? null : r.retry_rate <= 0.1 ? "ok" : r.retry_rate <= 0.25 ? "warn" : "bad";
  const faceHealth: Health | null =
    rel.avg_face_score == null
      ? null
      : rel.avg_face_score >= 80
        ? "ok"
        : rel.avg_face_score >= 65
          ? "warn"
          : "bad";

  const nothingYet = totalUsd === 0 && rel.clips_total === 0;

  if (nothingYet) {
    return (
      <p className="rounded-xl border hairline bg-card px-5 py-8 text-center text-sm text-zinc-500">
        No usage in this range yet. Generate a script or render a drama and the
        ledger starts filling in.
      </p>
    );
  }

  return (
    <>
      {/* ── 1 · routing efficiency ── */}
      <section className="space-y-4">
        <SectionTitle>Routing efficiency</SectionTitle>
        <div className="rounded-2xl border hairline bg-card p-6">
          <div className="flex flex-wrap items-end gap-x-10 gap-y-3">
            <div>
              <p className="text-5xl font-semibold tracking-tight">
                {Math.round(cheapPct)}%
              </p>
              <p className="mt-1 text-xs text-zinc-400">
                of language work ran on cheap tiers
              </p>
            </div>
            <div>
              <p className="text-2xl font-semibold text-ok">{fmtUsd(saved)}</p>
              <p className="mt-1 text-xs text-zinc-400">
                saved vs running everything on qwen-max
              </p>
            </div>
            <div className="text-xs tabular-nums text-zinc-500">
              {fmtTokens(data.llm.total_tokens)} tokens · actual{" "}
              {fmtUsd(data.llm.total_usd)} · all-premium would be{" "}
              {fmtUsd(data.llm.all_premium_usd)}
            </div>
          </div>
          <div className="mt-6">
            <TierSplitBar segments={segments.filter((s) => s.value > 0)} />
          </div>
          {cheapLeaders.length > 0 && (
            <p className="mt-4 text-xs text-zinc-400">
              Most work runs on {cheapLeaders.join(" and ")}; qwen-max is
              reserved for creative writing.
            </p>
          )}
        </div>
      </section>

      {/* ── 2 · the 13-model roster ── */}
      <section className="space-y-4">
        <SectionTitle>The 13-model roster</SectionTitle>
        <div className="grid gap-4 lg:grid-cols-2">
          {ROSTER.map((group) => {
            const subtotal = group.category
              ? cats[group.category]
              : { usd: data.llm.total_usd, quantity: data.llm.total_tokens };
            return (
              <div key={group.group} className="rounded-xl border hairline bg-card">
                <div className="flex items-center gap-2 border-b border-white/[0.06] px-4 py-2.5">
                  <span className="text-sm font-medium">{group.group}</span>
                  <span className="rounded-full bg-white/[0.05] px-2 py-0.5 text-[10px] text-zinc-500">
                    billed per {group.unit}
                  </span>
                  <span className="ml-auto text-xs tabular-nums text-zinc-400">
                    {subtotal ? fmtUsd(subtotal.usd) : "$0"}
                  </span>
                </div>
                <div className="divide-y divide-white/[0.04] px-4">
                  {group.models.map((m) => {
                    const row = byModel.get(m.name);
                    return (
                      <div key={m.name} className="flex items-baseline gap-3 py-2">
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-mono text-xs text-zinc-200">
                            {m.name}
                          </p>
                          <p className="truncate text-[10px] text-zinc-500">{m.role}</p>
                        </div>
                        <div className="shrink-0 text-right text-xs tabular-nums text-zinc-400">
                          {row ? (
                            <>
                              {fmtTokens(row.tokens)} tok
                              <span className="ml-2 text-zinc-500">{fmtUsd(row.usd)}</span>
                            </>
                          ) : group.category ? (
                            <span className="text-zinc-600" title="The ledger bills this group as a whole">
                              in group total
                            </span>
                          ) : (
                            <span className="text-zinc-600">unused</span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                  {/* premium vs economy ratio inside video — the routing story again */}
                  {group.group === "Video" && (wan || hh) && (
                    <div className="py-2.5">
                      <div className="mb-1 flex justify-between text-[10px] text-zinc-500">
                        <span>premium {wan?.clips ?? 0} clip{(wan?.clips ?? 0) === 1 ? "" : "s"}</span>
                        <span>economy {hh?.clips ?? 0} clip{(hh?.clips ?? 0) === 1 ? "" : "s"}</span>
                      </div>
                      <div className="flex h-2 w-full gap-[2px] overflow-hidden rounded-full">
                        <div
                          className="rounded-l-full bg-[#5b21b6]"
                          style={{
                            width: `${((wan?.clips ?? 0) / Math.max(1, (wan?.clips ?? 0) + (hh?.clips ?? 0))) * 100}%`,
                            minWidth: wan?.clips ? 3 : 0,
                          }}
                        />
                        <div className="flex-1 rounded-r-full bg-[#a78bfa]" />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── 3 · where the money goes ── */}
      <section className="space-y-4">
        <SectionTitle>Where the money goes</SectionTitle>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Total spent" value={fmtUsd(totalUsd)} />
          <Stat
            label="Avg per drama"
            value={data.dramas.length ? fmtUsd(totalUsd / data.dramas.length) : "—"}
            hint={`${data.dramas.length} drama${data.dramas.length === 1 ? "" : "s"} in range`}
          />
          <Stat
            label="Avg per minute of film"
            value={totalMinutes > 0 ? fmtUsd(totalUsd / totalMinutes) : "—"}
            hint={totalMinutes > 0 ? `${totalMinutes.toFixed(1)} min finished` : "no finished exports yet"}
          />
          <Stat
            label="Avg per clip"
            value={totalClips > 0 ? fmtUsd(totalUsd / totalClips) : "—"}
            hint={totalClips > 0 ? `${totalClips} clips` : undefined}
          />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border hairline bg-card p-5">
            <p className="mb-3 text-xs text-zinc-400">Spend by category</p>
            <RankedBars rows={catRows} />
            {videoShare >= 0.5 && (
              <p className="mt-3 text-[11px] text-zinc-500">
                Video is {fmtPct(videoShare)} of all spend, which is normal:
                rendering footage costs orders of magnitude more than tokens.
              </p>
            )}
          </div>
          <div className="rounded-xl border hairline bg-card p-5">
            <p className="mb-3 text-xs text-zinc-400">Spend by drama</p>
            <RankedBars rows={dramaRows} />
          </div>
        </div>
      </section>

      {/* ── 4 · reliability ── */}
      <section className="space-y-4">
        <SectionTitle>Reliability</SectionTitle>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <HealthCard
            label="Continuity pass rate"
            value={rel.continuity_pass_rate != null ? fmtPct(rel.continuity_pass_rate) : "—"}
            health={passHealth}
            note={
              rel.flagged > 0
                ? `${rel.flagged} clip${rel.flagged === 1 ? "" : "s"} flagged for review`
                : "scored by qwen3-vl-plus"
            }
          />
          <HealthCard
            label="Wan retry rate"
            value={wan ? fmtPct(wan.retry_rate) : "—"}
            health={retryHealth(wan)}
            note={wan ? `${wan.retried} of ${wan.clips} clips retried` : "no Wan clips in range"}
          />
          <HealthCard
            label="HappyHorse retry rate"
            value={hh ? fmtPct(hh.retry_rate) : "—"}
            health={retryHealth(hh)}
            note={hh ? `${hh.retried} of ${hh.clips} clips retried` : "no HappyHorse clips in range"}
          />
          <HealthCard
            label="Face-lock consistency"
            value={rel.avg_face_score != null ? `${Math.round(rel.avg_face_score)}` : "—"}
            health={faceHealth}
            note="avg face score across scored clips"
          />
        </div>
      </section>

      {/* ── 5 · trend ── */}
      <section className="space-y-4">
        <SectionTitle>Trend</SectionTitle>
        <div className="rounded-xl border hairline bg-card p-5">
          <TrendChart data={data.trend} reduced={reduced} />
        </div>
      </section>
    </>
  );
}
