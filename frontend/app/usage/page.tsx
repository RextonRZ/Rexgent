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
import { ForecastSandbox } from "@/components/usage/ForecastSandbox";
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
 * light mass of the violet ramp IS the routing win. Ink per fill luminance. */
const TIER_META = [
  { key: "qwen-flash", short: "flash", role: "cheap structured work", color: "#ddd6fe", ink: "#1c1633" },
  { key: "qwen-plus", short: "plus", role: "judgment + chat", color: "#a78bfa", ink: "#1c1633" },
  { key: "qwen3-vl-plus", short: "vl-plus", role: "continuity vision", color: "#8b5cf6", ink: "#f4f1ff" },
  { key: "qwen-max", short: "max", role: "creative writing", color: "#7c3aed", ink: "#f4f1ff" },
  { key: "qwen-vl-max", short: "vl-max", role: "reference analysis", color: "#5b21b6", ink: "#f4f1ff" },
];

interface RosterModel {
  name: string;
  role: string;
  /** ledger model keys whose usage sums onto this row */
  match?: string[];
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
      { name: "happyhorse-1.1-r2v", role: "HappyHorse · faces, dialogue, native speech", match: ["happyhorse-1.1", "happyhorse_fast"] },
      { name: "wan2.7-i2v", role: "Wan · silent continuations, scenery, silent multishot beats", match: ["wan2.7"] },
      { name: "happyhorse-1.0-video-edit", role: "Fix a take, the regen loop", match: ["happyhorse-1.0-video-edit"] },
    ],
  },
  {
    group: "Image",
    unit: "image",
    category: "image",
    icon: ImageIcon,
    tint: "text-indigo-300/70",
    models: [
      { name: "wan2.6-t2i", role: "Reference plates — character, location, style", match: ["wan2.6-t2i"] },
      { name: "qwen-image-edit-max", role: "Costume plates and frame edits", match: ["qwen-image-edit-max"] },
    ],
  },
  {
    group: "Voice",
    unit: "character",
    category: "tts",
    icon: AudioWaveform,
    tint: "text-sky-300/60",
    models: [
      { name: "qwen3-tts-vd", role: "Designed voices — bespoke timbre per character", match: ["qwen3-tts-vd-2026-01-26"] },
      { name: "qwen-voice-design", role: "Voice design — casting writes each voice from age and personality", match: ["qwen-voice-design"] },
      { name: "qwen3-tts-flash", role: "Preset voices + instruct acting delivery", match: ["qwen3-tts-flash"] },
      { name: "qwen3-tts-vc-realtime", role: "Cloned voices", match: ["qwen3-tts-vc-realtime"] },
      { name: "qwen-voice-enrollment", role: "Clone enrollment" },
    ],
  },
];

/** Section header with a hairline running off to the right — sections stop
 * blurring together without shouting. */
/** Sum a roster row's ledger models; null when nothing recorded for it. */
function mediaUsage(
  byModel: Record<string, { usd: number; quantity: number }> | undefined,
  match?: string[]
): { usd: number; quantity: number } | null {
  if (!byModel || !match?.length) return null;
  let usd = 0;
  let quantity = 0;
  for (const key of match) {
    const row = byModel[key];
    if (row) {
      usd += row.usd;
      quantity += row.quantity;
    }
  }
  return usd > 0 || quantity > 0 ? { usd, quantity } : null;
}

function fmtMediaQty(q: number, unit: string): string {
  if (unit === "second") return `${Math.round(q)}s`;
  if (unit === "image") return `${Math.round(q)} img`;
  if (unit === "character") return `${fmtTokens(q)} chars`;
  return String(Math.round(q));
}

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
 * never a gallery. Hover names the drama and shot. Expired footage never
 * renders as a black void: failed tiles drop out and a "+N expired" chip
 * counts them instead.
 * TODO(data): clips expire on OSS, so historical evidence breaks — persist a
 * small extracted poster JPG per clip at generation time and reference that
 * here instead of the live clip URL. */
function EvidenceStrip({ samples }: { samples?: ClipSample[] }) {
  const [failed, setFailed] = useState<Set<string>>(new Set());
  if (!samples?.length) return null;
  const ok = samples.filter((s) => !failed.has(s.url));
  // unavailable footage simply doesn't render — the stat stands on its own
  if (ok.length === 0) return null;
  return (
    <div className="mt-2.5 flex items-center gap-1.5">
      {ok.map((s, i) => {
        const tip = `${s.title}${s.shot_number != null ? ` · shot ${s.shot_number}` : ""}`;
        const cls =
          "h-8 w-12 shrink-0 rounded-[3px] bg-zinc-900 object-cover ring-1 ring-white/10";
        // the persisted still outlives the clip URL — use it when we have it
        return s.poster ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={`${s.url}-${i}`}
            src={s.poster}
            alt=""
            loading="lazy"
            onError={() => setFailed((prev) => new Set(prev).add(s.url))}
            title={tip}
            className={cls}
          />
        ) : (
          <video
            key={`${s.url}-${i}`}
            src={s.url}
            muted
            playsInline
            preload="metadata"
            onError={() => setFailed((prev) => new Set(prev).add(s.url))}
            title={tip}
            className={cls}
          />
        );
      })}
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
              Qwen Cloud models, routed by task. This page proves the routing
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
  const segments: TierSegment[] = TIER_META.map((t) => ({
    key: t.key,
    label: t.key,
    short: t.short,
    role: t.role,
    color: t.color,
    ink: t.ink,
    value: byModel.get(t.key)?.tokens ?? 0,
    usd: byModel.get(t.key)?.usd ?? 0,
  }));
  // fold anything the router doesn't know into ONE labeled gray tail, so the
  // bar always sums to 100% with every segment named in the legend
  const known = new Set(TIER_META.map((t) => t.key));
  const extras = data.llm.by_model.filter((r) => !known.has(r.model));
  if (extras.length) {
    segments.push({
      key: "other",
      label: "other",
      short: "other",
      role: extras.map((r) => r.model).join(", "),
      color: "#52525b",
      ink: "#e4e4e7",
      value: extras.reduce((s, r) => s + r.tokens, 0),
      usd: extras.reduce((s, r) => s + r.usd, 0),
    });
  }

  const cheapPct = useCountUp(Math.round(data.llm.cheap_share * 100), reduced);
  const saved = useCountUp(data.llm.saved_usd, reduced);

  const cats = data.categories;
  const catRows = (
    [
      ["Video", "video", (q: number) => `${Math.round(q)}s of footage`],
      ["Language", "llm", (q: number) => `${fmtTokens(q)} tokens`],
      ["Image", "image", (q: number) => `${Math.round(q)} images`],
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

  // dead voice spend stays in the ledger for history but is excluded here
  const totalUsd = Object.entries(cats).reduce(
    (s, [k, c]) => (k === "tts" ? s : s + c.usd),
    0
  );
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
  // Two video models: Wan renders the visuals, HappyHorse the characters. Each
  // keeps its own retry bucket; a drama may be all one model, so a card shows
  // only when its bucket has clips.
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
                    "h-full w-full min-w-0 flex-1 object-cover object-[50%_25%] opacity-25 brightness-[0.12]",
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
              {/* one baseline: the number and its context read as a unit */}
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <p className="text-[52px] font-medium leading-none tracking-tight">
                  {Math.round(cheapPct)}
                  <span className="text-[26px] text-zinc-400">%</span>
                </p>
                <p className="text-sm text-zinc-400">
                  of language work on cheap tiers ·{" "}
                  <span
                    className="font-medium text-ok"
                    style={{ textShadow: "0 0 20px rgba(74,222,128,0.3)" }}
                  >
                    {fmtUsd(saved)} saved
                  </span>
                </p>
              </div>
              <div className="mt-4">
                <TierSplitBar segments={segments} />
              </div>
              {/* the receipt, small */}
              <p className="mt-3 text-[10px] tabular-nums text-zinc-600">
                {fmtTokens(data.llm.total_tokens)} tokens · actual{" "}
                {fmtUsd(data.llm.total_usd)} · all-premium would be{" "}
                {fmtUsd(data.llm.all_premium_usd)}
              </p>
            </div>
            <Sprockets />
          </div>
        </div>
      </Rise>

      {/* ── 2 · the 13-model roster: the crew list ── */}
      <Rise index={1}>
        <SectionTitle>The model roster</SectionTitle>
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
                    const media = mediaUsage(
                      group.category ? cats[group.category]?.by_model : undefined,
                      m.match
                    );
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
                          ) : media ? (
                            <>
                              {fmtMediaQty(media.quantity, group.unit)}
                              <span className="ml-2 text-zinc-500">{fmtUsd(media.usd)}</span>
                            </>
                          ) : group.category ? (
                            <span
                              className="text-zinc-600"
                              title="No usage recorded for this model in the selected range"
                            >
                              unused
                            </span>
                          ) : (
                            <span className="text-zinc-600">unused</span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                  {group.group === "Video" && (wan || hh) && (
                    <p className="py-3 text-[10px] text-zinc-500">
                      {(wan?.clips ?? 0) + (hh?.clips ?? 0)} clip
                      {(wan?.clips ?? 0) + (hh?.clips ?? 0) === 1 ? "" : "s"}{" "}
                      rendered in this range
                      {wan && hh
                        ? `: ${wan.clips} on Wan, ${hh.clips} on HappyHorse`
                        : "."}
                    </p>
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
          {hh && (
            <HealthCard
              label="HappyHorse retries"
              value={fmtPct(hh.retry_rate)}
              health={retryHealth(hh)}
              note={`${hh.retried} of ${hh.clips} clips retried`}
            />
          )}
          {wan && (
            <HealthCard
              label="Wan retries"
              value={fmtPct(wan.retry_rate)}
              health={retryHealth(wan)}
              note={`${wan.retried} of ${wan.clips} clips retried`}
            />
          )}
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

      {/* ── 6 · forecast ── */}
      <Rise index={5}>
        <SectionTitle>Forecast</SectionTitle>
        <ForecastSandbox data={data} />
      </Rise>
    </>
  );
}
