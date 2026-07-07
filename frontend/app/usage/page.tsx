"use client";

import { useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  AudioWaveform,
  CheckCircle2,
  Clapperboard,
  Film,
  Image as ImageIcon,
  MessageSquareText,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { UserMenu } from "@/components/auth/UserMenu";
import { AmbientBackdrop } from "@/components/shared/AmbientBackdrop";
import { GRAIN } from "@/components/landing/CtaBackdrop";
import { GENRES } from "@/lib/genres";
import { useReducedMotion } from "@/hooks/useReducedMotion";
import { useCountUp } from "@/hooks/useCountUp";
import {
  useUsageAnalytics,
  type ClipSample,
  type UsageAnalytics,
  type UsageRange,
} from "@/hooks/useUsageAnalytics";
import {
  RankedBars,
  TierRatioBar,
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
  icon: LucideIcon;
  tint: string; // low-sat icon tint — cohesive, not colorful
  models: RosterModel[];
}[] = [
  {
    group: "Language",
    unit: "token",
    category: null,
    icon: MessageSquareText,
    tint: "text-violet-300/70",
    models: [
      { name: "qwen-max", role: "Creative writing — script and shot direction" },
      { name: "qwen-plus", role: "Judgment — narrative judge, chat, relationships" },
      { name: "qwen-flash", role: "Structured work — parsing, extraction, wardrobe, titles" },
      { name: "qwen3-vl-plus", role: "Continuity vision — face and scene drift scoring" },
      { name: "qwen-vl-max", role: "Reference photo and appearance analysis" },
    ],
  },
  {
    group: "Video",
    unit: "second",
    category: "video",
    icon: Film,
    tint: "text-fuchsia-300/60",
    models: [
      { name: "wan2.7-t2v / i2v", role: "Premium tier — the shots that matter" },
      { name: "happyhorse-1.1-t2v / i2v / r2v", role: "Economy tier — supporting shots" },
      { name: "happyhorse-1.0-video-edit", role: "Fix a take — the regen loop" },
    ],
  },
  {
    group: "Image",
    unit: "image",
    category: "image",
    icon: ImageIcon,
    tint: "text-indigo-300/70",
    models: [
      { name: "wan2.6-t2i", role: "Reference plates — character, location, style" },
      { name: "qwen-image-edit-max", role: "Costume plates and frame edits" },
    ],
  },
  {
    group: "Voice",
    unit: "character",
    category: "tts",
    icon: AudioWaveform,
    tint: "text-sky-300/60",
    models: [
      { name: "qwen3-tts-flash", role: "Preset voices" },
      { name: "qwen3-tts-vc-realtime", role: "Cloned voices" },
      { name: "qwen-voice-enrollment", role: "Clone enrollment" },
    ],
  },
];

/** Section header with a hairline running off to the right — sections stop
 * blurring together without shouting. */
function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-4">
      <h2 className="shrink-0 text-xs font-medium uppercase tracking-widest text-zinc-500">
        {children}
      </h2>
      <span aria-hidden className="h-px flex-1 bg-white/[0.06]" />
    </div>
  );
}

/** Film-frame sprockets, same language as the dashboard recap shelf. */
function Sprockets() {
  return (
    <div
      aria-hidden
      className="flex w-6 shrink-0 flex-col items-center justify-center gap-4 py-3"
    >
      {Array.from({ length: 7 }).map((_, i) => (
        <span key={i} className="h-[9px] w-[7px] rounded-[2px] bg-zinc-800" />
      ))}
    </div>
  );
}

/** Drama poster thumb — the same art the dashboard cards lead with; a
 * genre-tinted placeholder when no poster was extracted yet. */
function PosterThumb({
  poster,
  genre,
}: {
  poster: string | null;
  genre: string | null;
}) {
  if (poster) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={poster}
        alt=""
        loading="lazy"
        className="h-9 w-7 shrink-0 rounded-[4px] object-cover object-[50%_25%] ring-1 ring-white/10"
      />
    );
  }
  const g = GENRES.find((x) => x.value === (genre || "").toLowerCase());
  const Icon = g?.icon ?? Clapperboard;
  return (
    <span
      className="flex h-9 w-7 shrink-0 items-center justify-center rounded-[4px] ring-1 ring-white/10"
      style={{ background: g?.tint ?? "hsl(250 12% 13%)" }}
    >
      <Icon className="size-3 text-zinc-500" />
    </span>
  );
}

/** The clips BEHIND a reliability number — visible proof, sized as evidence,
 * never a gallery. Hover names the drama and shot. */
function EvidenceStrip({ samples }: { samples?: ClipSample[] }) {
  if (!samples?.length) return null;
  return (
    <div className="mt-2.5 flex gap-1.5">
      {samples.map((s, i) => (
        <video
          key={`${s.url}-${i}`}
          src={s.url}
          muted
          playsInline
          preload="metadata"
          title={`${s.title}${s.shot_number != null ? ` · shot ${s.shot_number}` : ""}`}
          className="h-8 w-12 shrink-0 rounded-[3px] object-cover ring-1 ring-white/10"
        />
      ))}
    </div>
  );
}

/** Dashboard-style stat card: hover lift + a reserved sub-label that fades in. */
function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="group rounded-xl border border-white/[0.08] bg-white/[0.02] px-3 pb-2.5 pt-4 text-center transition-all duration-150 hover:border-white/15 motion-safe:hover:-translate-y-0.5 motion-reduce:transition-none">
      <p className="text-2xl font-semibold text-foreground">{value}</p>
      <p className="mt-1 text-[10px] uppercase tracking-widest text-zinc-500">
        {label}
      </p>
      {/* reserved slot — fades in on hover, never reflows */}
      <p className="mt-0.5 h-3.5 truncate text-[10px] leading-[14px] text-zinc-600 opacity-0 transition-opacity duration-150 group-hover:opacity-100 motion-reduce:transition-none">
        {sub ?? ""}
      </p>
    </div>
  );
}

type Health = "ok" | "warn" | "bad";
function HealthCard({
  label,
  value,
  health,
  note,
  evidence,
}: {
  label: string;
  value: string | null;
  health: Health | null;
  note?: string;
  /** the actual clips behind the number — rendered only when there is data */
  evidence?: React.ReactNode;
}) {
  const Icon =
    health === "ok" ? CheckCircle2 : health === "warn" ? AlertTriangle : XCircle;
  return (
    <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] px-4 py-3.5 transition-all duration-150 hover:border-white/15 motion-safe:hover:-translate-y-0.5 motion-reduce:transition-none">
      <p className="text-[10px] uppercase tracking-widest text-zinc-500">{label}</p>
      {value ? (
        <p className="mt-1 flex items-center gap-2 text-xl font-semibold">
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
      ) : (
        <p className="mt-1 text-xl font-medium text-zinc-700">—</p>
      )}
      <p className="mt-0.5 text-[10px] text-zinc-500">
        {value ? note : "no data in this range yet"}
      </p>
      {value ? evidence : null}
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
      <AmbientBackdrop />
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

      <div className="mx-auto max-w-5xl space-y-14 px-6 pb-20 pt-10">
        {/* masthead — quiet; the routing hero below carries the drama */}
        <div className="card-rise flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              Usage &amp; analytics
            </h1>
            <p className="mt-1 max-w-xl text-sm text-zinc-500">
              13 Qwen Cloud models, routed by task. This page proves the routing
              works and shows where the money goes.
            </p>
          </div>
          <div
            className="flex rounded-lg border hairline bg-black/20 p-0.5"
            role="tablist"
            aria-label="Time range"
          >
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
        </div>

        {isLoading || !data ? (
          <p className="text-sm text-zinc-500">Reading the ledger…</p>
        ) : (
          <Dashboard data={data} reduced={reduced} />
        )}
      </div>
    </main>
  );
}

/** Staggered section entrance, same card-rise the dashboard uses. */
function Rise({
  index,
  children,
  className,
}: {
  index: number;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn("card-rise space-y-4", className)}
      style={{ animationDelay: `${index * 90}ms` }}
    >
      {children}
    </section>
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
  const totalUp = useCountUp(totalUsd, reduced);

  const dramaRows = data.dramas.slice(0, 8).map((d) => ({
    label: d.title,
    value: d.usd,
    display: fmtUsd(d.usd),
    sub: d.usd_per_min != null ? `${fmtUsd(d.usd_per_min)}/min of film` : undefined,
    thumb: <PosterThumb poster={d.poster_url} genre={d.genre} />,
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
      <p className="card-rise rounded-xl border hairline bg-card px-5 py-10 text-center text-sm text-zinc-500">
        No usage in this range yet. Generate a script or render a drama and the
        ledger starts filling in.
      </p>
    );
  }

  return (
    <>
      {/* ── 1 · routing efficiency: the screening-room hero ── */}
      <Rise index={0}>
        <SectionTitle>Routing efficiency</SectionTitle>
        <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-[#0c0a15] shadow-[0_20px_60px_-20px_rgba(0,0,0,0.8)]">
          {/* faint montage of the user's own productions — atmosphere, not
           * content: heavily darkened, masked away before the numbers */}
          {(data.hero_stills?.length ?? 0) > 0 && (
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0 flex"
              style={{
                WebkitMaskImage:
                  "linear-gradient(to bottom, rgba(0,0,0,0.8), transparent 80%)",
                maskImage:
                  "linear-gradient(to bottom, rgba(0,0,0,0.8), transparent 80%)",
              }}
            >
              {data.hero_stills!.map((u, i) => (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  key={`${u}-${i}`}
                  src={u}
                  alt=""
                  loading="lazy"
                  className={cn(
                    "h-full w-full min-w-0 flex-1 object-cover object-[50%_25%] opacity-30 brightness-[0.25]",
                    !reduced && "animate-[ken-burns_16s_ease-out_forwards]"
                  )}
                />
              ))}
            </div>
          )}
          {/* screening-room glow behind the numbers only */}
          <div
            aria-hidden
            className="pointer-events-none absolute -top-24 left-1/4 h-72 w-2/3 rounded-full bg-violet-600/[0.13] blur-[90px]"
          />
          {/* film grain over the panel */}
          <div
            aria-hidden
            className={cn(
              "pointer-events-none absolute inset-0 opacity-[0.05] mix-blend-overlay",
              !reduced && "animate-[film-grain_0.8s_steps(1)_infinite]"
            )}
            style={{ backgroundImage: GRAIN }}
          />
          <div className="relative flex items-stretch">
            <Sprockets />
            <div className="min-w-0 flex-1 px-2 py-7 sm:px-4">
              <div className="flex flex-wrap items-end gap-x-12 gap-y-4">
                <div>
                  <p className="text-7xl font-semibold leading-none tracking-tight sm:text-8xl">
                    {Math.round(cheapPct)}
                    <span className="text-4xl text-zinc-400 sm:text-5xl">%</span>
                  </p>
                  <p className="mt-2 text-sm text-zinc-400">
                    of language work ran on cheap tiers
                  </p>
                </div>
                <div>
                  <p
                    className="text-4xl font-semibold text-ok"
                    style={{ textShadow: "0 0 28px rgba(74,222,128,0.35)" }}
                  >
                    {fmtUsd(saved)}
                  </p>
                  <p className="mt-2 text-sm text-zinc-400">
                    saved vs running everything on qwen-max
                  </p>
                </div>
                <p className="pb-1 text-xs tabular-nums text-zinc-600">
                  {fmtTokens(data.llm.total_tokens)} tokens · actual{" "}
                  {fmtUsd(data.llm.total_usd)} · all-premium would be{" "}
                  {fmtUsd(data.llm.all_premium_usd)}
                </p>
              </div>
              <div className="mt-8">
                <TierSplitBar segments={segments.filter((s) => s.value > 0)} />
              </div>
              {cheapLeaders.length > 0 && (
                <p className="mt-5 text-xs italic text-zinc-500">
                  Most work runs on {cheapLeaders.join(" and ")}; qwen-max is
                  reserved for creative writing.
                </p>
              )}
            </div>
            <Sprockets />
          </div>
        </div>
      </Rise>

      {/* ── 2 · the 13-model roster: the crew list ── */}
      <Rise index={1}>
        <SectionTitle>The 13-model roster</SectionTitle>
        <div className="gap-4 lg:columns-2">
          {ROSTER.map((group) => {
            const subtotal = group.category
              ? cats[group.category]
              : { usd: data.llm.total_usd, quantity: data.llm.total_tokens };
            const GroupIcon = group.icon;
            return (
              <div
                key={group.group}
                className="mb-4 break-inside-avoid overflow-hidden rounded-xl border border-white/[0.08] bg-white/[0.02]"
              >
                <div className="flex items-center gap-2 border-b border-white/[0.06] bg-white/[0.015] px-4 py-2.5">
                  <GroupIcon className={cn("size-3.5", group.tint)} />
                  <span className="text-sm font-medium">{group.group}</span>
                  <span className="rounded-full bg-white/[0.05] px-2 py-0.5 text-[10px] text-zinc-500">
                    billed per {group.unit}
                  </span>
                  <span className="ml-auto text-xs font-semibold tabular-nums text-zinc-300">
                    {subtotal ? fmtUsd(subtotal.usd) : "$0"}
                  </span>
                </div>
                <div className="divide-y divide-white/[0.04] px-4">
                  {group.models.map((m) => {
                    const row = byModel.get(m.name);
                    return (
                      <div key={m.name} className="flex items-baseline gap-3 py-2.5">
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
                            <span
                              className="text-zinc-600"
                              title="The ledger bills this group as a whole"
                            >
                              in group total
                            </span>
                          ) : (
                            <span className="text-zinc-600">unused</span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                  {/* premium vs economy — the routing story again */}
                  {group.group === "Video" && (wan || hh) && (
                    <div className="py-3">
                      <div className="mb-1.5 flex justify-between text-[10px] text-zinc-500">
                        <span>premium · {wan?.clips ?? 0} clip{(wan?.clips ?? 0) === 1 ? "" : "s"}</span>
                        <span>economy · {hh?.clips ?? 0} clip{(hh?.clips ?? 0) === 1 ? "" : "s"}</span>
                      </div>
                      <TierRatioBar
                        a={{ label: "Wan 2.7 (premium)", clips: wan?.clips ?? 0 }}
                        b={{ label: "HappyHorse 1.1 (economy)", clips: hh?.clips ?? 0 }}
                      />
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Rise>

      {/* ── 3 · where the money goes ── */}
      <Rise index={2}>
        <SectionTitle>Where the money goes</SectionTitle>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat
            label="Total spent"
            value={fmtUsd(totalUp)}
            sub={`across ${data.dramas.length} drama${data.dramas.length === 1 ? "" : "s"}`}
          />
          <Stat
            label="Avg per drama"
            value={data.dramas.length ? fmtUsd(totalUsd / data.dramas.length) : "—"}
            sub={data.dramas.length ? "script to final cut" : "no dramas in range"}
          />
          <Stat
            label="Per minute of film"
            value={totalMinutes > 0 ? fmtUsd(totalUsd / totalMinutes) : "—"}
            sub={
              totalMinutes > 0
                ? `${totalMinutes.toFixed(1)} min finished`
                : "no finished exports yet"
            }
          />
          <Stat
            label="Avg per clip"
            value={totalClips > 0 ? fmtUsd(totalUsd / totalClips) : "—"}
            sub={totalClips > 0 ? `${totalClips} clips rendered` : "no clips in range"}
          />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-5">
            <p className="mb-4 text-[10px] uppercase tracking-widest text-zinc-500">
              Spend by category
            </p>
            <RankedBars rows={catRows} />
            {videoShare >= 0.5 && (
              <p className="mt-4 text-[11px] italic text-zinc-500">
                Video is {fmtPct(videoShare)} of all spend, which is normal:
                rendering footage costs orders of magnitude more than tokens.
              </p>
            )}
          </div>
          <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-5">
            <p className="mb-4 text-[10px] uppercase tracking-widest text-zinc-500">
              Spend by drama
            </p>
            <RankedBars rows={dramaRows} />
          </div>
        </div>
      </Rise>

      {/* ── 4 · reliability ── */}
      <Rise index={3}>
        <SectionTitle>Reliability</SectionTitle>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <HealthCard
            label="Continuity pass"
            value={rel.continuity_pass_rate != null ? fmtPct(rel.continuity_pass_rate) : null}
            health={passHealth}
            note={
              rel.flagged > 0
                ? `${rel.flagged} clip${rel.flagged === 1 ? "" : "s"} flagged for review`
                : "scored by qwen3-vl-plus"
            }
            evidence={<EvidenceStrip samples={rel.flagged_samples} />}
          />
          <HealthCard
            label="Wan retries"
            value={wan ? fmtPct(wan.retry_rate) : null}
            health={retryHealth(wan)}
            note={wan ? `${wan.retried} of ${wan.clips} clips retried` : undefined}
          />
          <HealthCard
            label="HappyHorse retries"
            value={hh ? fmtPct(hh.retry_rate) : null}
            health={retryHealth(hh)}
            note={hh ? `${hh.retried} of ${hh.clips} clips retried` : undefined}
            evidence={<EvidenceStrip samples={rel.retried_samples} />}
          />
          <HealthCard
            label="Face lock"
            value={rel.avg_face_score != null ? String(Math.round(rel.avg_face_score)) : null}
            health={faceHealth}
            note="avg face score across scored clips"
          />
        </div>
      </Rise>

      {/* ── 5 · trend ── */}
      <Rise index={4}>
        <SectionTitle>Trend</SectionTitle>
        <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-5">
          <TrendChart data={data.trend} reduced={reduced} />
        </div>
      </Rise>
    </>
  );
}
