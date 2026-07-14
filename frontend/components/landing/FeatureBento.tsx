"use client";

import { useEffect, useRef, useState } from "react";
import {
  Check,
  Mic,
  Pencil,
  RefreshCw,
  Shirt,
  Trash2,
  UserRound,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useReducedMotion } from "@/hooks/useReducedMotion";

// Numbered in reading order: large row first, then the compact row.
const WOWS = [
  {
    k: "01",
    title: "Faces that never drift",
    body: "Upload one reference photo. Every clip is verified against a real facial embedding, and weak takes retry themselves until the face holds.",
  },
  {
    k: "02",
    title: "The budget is a feature",
    body: "A live meter spends full-quality generation only on the shots that matter, turning a hard limit into a smart allocator.",
  },
  {
    k: "03",
    title: "One premise, a whole drama",
    body: "An autonomous agent writes the script, judges its own draft, casts the characters, storyboards every scene and reports back. You watch a studio work for you.",
  },
  {
    k: "04",
    title: "Wardrobe built in",
    body: "Every character gets costume plates for each look in the story, so the same person walks through every scene wearing the right outfit.",
  },
  {
    k: "05",
    title: "Clone your voice",
    body: "Read one short passage into your mic and your characters speak with your voice, or pick from a catalog of studio presets.",
  },
  {
    k: "06",
    title: "You stay the director",
    body: "Edit the script, swap faces, redo plates, delete shots, regenerate clips. The agent runs the pipeline while you keep creative control.",
  },
];

/** Card shell: quiet chrome plus a faint radial highlight under the cursor. */
function GlowCard({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  return (
    <div
      ref={ref}
      onMouseMove={(e) => {
        const el = ref.current;
        if (!el) return;
        const r = el.getBoundingClientRect();
        el.style.setProperty("--x", `${e.clientX - r.left}px`);
        el.style.setProperty("--y", `${e.clientY - r.top}px`);
      }}
      className={cn(
        "group relative overflow-hidden rounded-2xl border border-white/[0.08] bg-zinc-900/60 p-6",
        "transition-colors duration-300 hover:border-white/15",
        className
      )}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{
          background:
            "radial-gradient(220px circle at var(--x, 50%) var(--y, 50%), rgba(255,255,255,0.04), transparent 70%)",
        }}
      />
      <div className="relative">{children}</div>
    </div>
  );
}

function CardText({
  k,
  title,
  body,
}: {
  k: string;
  title: string;
  body: string;
}) {
  return (
    <>
      <span className="text-xs font-mono text-primary/70">{k}</span>
      <h3 className="mt-2 font-semibold">{title}</h3>
      <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
        {body}
      </p>
    </>
  );
}

/** Reference chip + four frames; a scan line sweeps and checks pop per frame. */
function FaceScanStrip({ reduced }: { reduced: boolean }) {
  const frames = ["/poster1.jpg", "/poster5.jpg", "/poster7.jpg", "/poster12.jpg"];
  return (
    <div className="mt-6 flex items-center gap-3">
      <div className="flex shrink-0 flex-col items-center gap-1">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/refimg.png"
          alt=""
          className="h-12 w-12 rounded-md border border-white/15 object-cover"
        />
        <span className="text-[9px] uppercase tracking-widest text-muted-foreground">
          Ref
        </span>
      </div>
      <div className="relative min-w-0 flex-1">
        <div className="flex gap-1.5">
          {frames.map((src, i) => (
            <div
              key={src}
              className="relative min-w-0 flex-1 overflow-hidden rounded-[3px] border border-white/10"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={src}
                alt=""
                loading="lazy"
                className="aspect-video w-full object-cover"
              />
              <span
                className={cn(
                  "absolute right-1 top-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-emerald-500/90 text-black",
                  reduced
                    ? "opacity-100"
                    : "opacity-0 animate-[scan-check_4s_linear_infinite]"
                )}
                style={
                  reduced ? undefined : { animationDelay: `${0.5 + i}s` }
                }
              >
                <Check className="size-2.5" strokeWidth={3.5} />
              </span>
            </div>
          ))}
        </div>
        {!reduced && (
          <span
            aria-hidden
            className="absolute inset-y-0 w-0.5 bg-violet-400/90 shadow-[0_0_8px_rgba(139,92,246,0.9)] animate-[scan-sweep_4s_linear_infinite]"
          />
        )}
      </div>
    </div>
  );
}

const BUDGET_TARGET = 2.77;
const BUDGET_CAP = 40;
const BUDGET_ROWS = [
  { label: "Video", share: 0.76 },
  { label: "Image", share: 0.16 },
  { label: "TTS", share: 0.08 },
];

/** Mini live-cost meter: counts up once when it scrolls into view. */
function BudgetMeterMini({ reduced }: { reduced: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const started = useRef(false);
  const [val, setVal] = useState(0);

  useEffect(() => {
    if (reduced) {
      setVal(BUDGET_TARGET);
      return;
    }
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => {
        if (!e.isIntersecting || started.current) return;
        started.current = true;
        const t0 = performance.now();
        const dur = 1800;
        const tick = (t: number) => {
          const p = Math.min(1, (t - t0) / dur);
          const eased = 1 - Math.pow(1 - p, 3);
          setVal(BUDGET_TARGET * eased);
          if (p < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      },
      { threshold: 0.4 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [reduced]);

  const frac = val / BUDGET_TARGET || 0;

  return (
    <div ref={ref} className="mt-6 space-y-3">
      <div className="flex items-baseline justify-between">
        <span className="text-[11px] uppercase tracking-widest text-muted-foreground">
          Live budget
        </span>
        <span className="font-mono text-sm">
          <span className="text-foreground">${val.toFixed(2)}</span>
          <span className="text-muted-foreground"> / ${BUDGET_CAP.toFixed(2)}</span>
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/5">
        <div
          className="h-full rounded-full bg-violet-500"
          style={{ width: `${(val / BUDGET_CAP) * 100}%` }}
        />
      </div>
      <div className="space-y-1.5 pt-1">
        {BUDGET_ROWS.map((row) => (
          <div key={row.label} className="flex items-center gap-3">
            <span className="w-10 text-[11px] text-muted-foreground">
              {row.label}
            </span>
            <div className="h-1 flex-1 overflow-hidden rounded-full bg-white/5">
              <div
                className="h-full rounded-full bg-violet-500/60"
                style={{ width: `${row.share * 100 * frac}%` }}
              />
            </div>
            <span className="w-12 text-right font-mono text-[11px] text-muted-foreground">
              ${(val * row.share).toFixed(2)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Agent pipeline chips lighting up in sequence: write, judge, cast, board. */
function PipelineTrace({ reduced }: { reduced: boolean }) {
  const steps = ["Write", "Judge", "Cast", "Board"];
  return (
    <div className="mt-5 flex flex-wrap items-center gap-1.5">
      {steps.map((s, i) => (
        <span
          key={s}
          className={cn(
            "rounded-full px-2.5 py-1 text-[10px] font-medium",
            reduced && i === 0
              ? "bg-violet-500/25 text-violet-300"
              : "bg-white/5 text-zinc-400",
            !reduced && "animate-[step-glow_4.8s_linear_infinite]"
          )}
          style={!reduced ? { animationDelay: `${i * 1.2}s` } : undefined}
        >
          {s}
        </span>
      ))}
    </div>
  );
}

/** Same face, three looks: outfit plate chips with the active one lit. */
function WardrobeRow() {
  return (
    <div className="mt-5 flex items-center gap-2">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-md border",
            i === 1
              ? "border-violet-400/50 bg-violet-500/15 text-violet-300"
              : "border-white/10 bg-white/5 text-zinc-400"
          )}
        >
          <Shirt className="size-3.5" />
        </span>
      ))}
      <span className="ml-1 text-[10px] text-muted-foreground">
        1 face · 3 looks
      </span>
    </div>
  );
}

/** Mic + a small equalizer that breathes. */
function VoiceWave({ reduced }: { reduced: boolean }) {
  const heights = [6, 10, 15, 9, 17, 7, 12, 18, 10, 14, 6, 11];
  return (
    <div className="mt-5 flex items-center gap-3">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-white/10 bg-white/5 text-zinc-400">
        <Mic className="size-3.5" />
      </span>
      <div className="flex h-5 items-center gap-[3px]">
        {heights.map((h, i) => (
          <span
            key={i}
            className={cn(
              "w-[3px] rounded-full bg-violet-400/70",
              !reduced && "animate-[voice-bar_1.3s_ease-in-out_infinite]"
            )}
            style={{
              height: `${h}px`,
              animationDelay: !reduced ? `${i * 0.09}s` : undefined,
            }}
          />
        ))}
      </div>
    </div>
  );
}

/** The director's toolbar: edit, recast, regenerate, cut. */
function DirectorTools() {
  const tools = [Pencil, UserRound, RefreshCw, Trash2];
  return (
    <div className="mt-5 flex items-center gap-2">
      {tools.map((Icon, i) => (
        <span
          key={i}
          className="flex h-8 w-8 items-center justify-center rounded-md border border-white/10 bg-white/5 text-zinc-400 transition-colors group-hover:text-zinc-300"
        >
          <Icon className="size-3.5" />
        </span>
      ))}
    </div>
  );
}

export function FeatureBento() {
  const reduced = useReducedMotion();

  return (
    <section id="features" className="mx-auto max-w-6xl px-6 pb-28">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-12">
        <GlowCard className="md:col-span-7">
          <CardText {...WOWS[0]} />
          <FaceScanStrip reduced={reduced} />
        </GlowCard>

        <GlowCard className="md:col-span-5">
          <CardText {...WOWS[1]} />
          <BudgetMeterMini reduced={reduced} />
        </GlowCard>

        <GlowCard className="md:col-span-3">
          <CardText {...WOWS[2]} />
          <PipelineTrace reduced={reduced} />
        </GlowCard>

        <GlowCard className="md:col-span-3">
          <CardText {...WOWS[3]} />
          <WardrobeRow />
        </GlowCard>

        <GlowCard className="md:col-span-3">
          <CardText {...WOWS[4]} />
          <VoiceWave reduced={reduced} />
        </GlowCard>

        <GlowCard className="md:col-span-3">
          <CardText {...WOWS[5]} />
          <DirectorTools />
        </GlowCard>
      </div>
    </section>
  );
}
