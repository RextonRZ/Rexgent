"use client";

import { useEffect, useRef, useState } from "react";
import {
  Check,
  FileText,
  Pencil,
  PenLine,
  RefreshCw,
  Shirt,
  Trash2,
  UserRound,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useReducedMotion } from "@/hooks/useReducedMotion";
import { VISUAL_STYLES } from "@/lib/styles";

// every non-photoreal look, cycled on the styles tile
const STYLE_REEL = VISUAL_STYLES.filter((s) => s.value !== "photoreal");

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
    title: `${VISUAL_STYLES.length} visual styles`,
    body: "Photoreal cinema, Ghibli softness, anime, pixel art, claymation. Pick a look when you create the drama and every plate, poster and clip renders in it.",
  },
  {
    k: "04",
    title: "A premise or a script, a whole drama",
    body: "Type one line and an autonomous agent writes the screenplay, or import the script you already have as PDF, DOCX or Fountain. Either way it judges the draft, casts the characters, storyboards every scene and reports back.",
  },
  {
    k: "05",
    title: "Wardrobe built in",
    body: "Every character gets costume plates for each look in the story, so the same person walks through every scene wearing the right outfit.",
  },
  {
    k: "06",
    title: "Characters that speak",
    body: "Every character speaks their lines with the mouth moving in time, generated with the shot so the voice lands on the picture instead of being dubbed on afterward.",
  },
  {
    k: "07",
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
  { label: "Video", share: 0.82 },
  { label: "Image", share: 0.18 },
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

/** Two ways in (a typed premise, an imported script file) feeding one agent
 * pipeline: the input chips take turns lighting, then the steps run in
 * sequence beneath them. Fills the wide tile with its own story. */
function TwoDoorsPipeline({ reduced }: { reduced: boolean }) {
  const steps = ["Write", "Judge", "Cast", "Board", "Render"];
  const door =
    "flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5 text-[11px] text-zinc-300";
  const fmt = "rounded bg-white/10 px-1 py-px text-[9px] text-zinc-400";
  return (
    <div className="mt-5 space-y-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={cn(door, !reduced && "animate-[step-glow_6s_linear_infinite]")}
        >
          <PenLine className="size-3 text-violet-300/80" />
          Type a premise
        </span>
        <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
          or
        </span>
        <span
          className={cn(door, !reduced && "animate-[step-glow_6s_linear_infinite]")}
          style={!reduced ? { animationDelay: "3s" } : undefined}
        >
          <FileText className="size-3 text-violet-300/80" />
          Import a script
          <span className={fmt}>PDF</span>
          <span className={fmt}>DOCX</span>
          <span className={fmt}>Fountain</span>
        </span>
      </div>
      {/* both doors land in the same pipeline */}
      <div className="flex items-center gap-2 pl-1">
        <span aria-hidden className="h-3 w-px bg-white/15" />
        <span className="text-[10px] text-muted-foreground">
          either way, the studio takes it from here
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {steps.map((s, i) => (
          <span
            key={s}
            className={cn(
              "rounded-full px-2.5 py-1 text-[10px] font-medium",
              reduced && i === 0
                ? "bg-violet-500/25 text-violet-300"
                : "bg-white/5 text-zinc-400",
              !reduced && "animate-[step-glow_6s_linear_infinite]"
            )}
            style={!reduced ? { animationDelay: `${i * 1.2}s` } : undefined}
          >
            {s}
          </span>
        ))}
      </div>
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

/** A character frame beside a breathing equalizer: the voice synced to the shot. */
function SpeechWave({ reduced }: { reduced: boolean }) {
  const heights = [6, 10, 15, 9, 17, 7, 12, 18, 10, 14, 6, 11];
  return (
    <div className="mt-5 flex items-center gap-3">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/poster5.jpg"
        alt=""
        loading="lazy"
        className="h-8 w-8 shrink-0 rounded-md border border-white/15 object-cover"
      />
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
      <span className="ml-1 text-[10px] text-muted-foreground">in sync</span>
    </div>
  );
}

/** The same drama cycling through the style catalog: crossfading stills with
 * the active look named beneath. Reduced motion shows a static four-up. */
function StyleReel({ reduced }: { reduced: boolean }) {
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    if (reduced) return;
    const t = window.setInterval(
      () => setIdx((i) => (i + 1) % STYLE_REEL.length),
      1800
    );
    return () => window.clearInterval(t);
  }, [reduced]);

  if (reduced) {
    return (
      <div className="mt-6 grid grid-cols-4 gap-1.5">
        {STYLE_REEL.slice(0, 4).map((s) => (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={s.value}
            src={`/styles/${s.value}.jpg`}
            alt={s.label}
            loading="lazy"
            className="aspect-video w-full rounded-[3px] border border-white/10 object-cover"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="mt-6">
      <div className="relative aspect-[16/8] overflow-hidden rounded-lg border border-white/10">
        {STYLE_REEL.map((s, i) => (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={s.value}
            src={`/styles/${s.value}.jpg`}
            alt=""
            loading={i < 3 ? "eager" : "lazy"}
            className={cn(
              "absolute inset-0 h-full w-full object-cover transition-opacity duration-700",
              i === idx ? "opacity-100" : "opacity-0"
            )}
          />
        ))}
        <span className="absolute bottom-1.5 left-1.5 rounded-full bg-black/60 px-2 py-0.5 text-[10px] font-medium text-white/90 backdrop-blur-sm">
          {STYLE_REEL[idx].label}
        </span>
        {/* the reel's progress dots, one per look, active one lit */}
        <span className="absolute bottom-2 right-2 flex gap-[3px]">
          {STYLE_REEL.slice(0, 8).map((_, i) => (
            <span
              key={i}
              className={cn(
                "h-1 w-1 rounded-full",
                i === idx % 8 ? "bg-violet-300" : "bg-white/25"
              )}
            />
          ))}
        </span>
      </div>
    </div>
  );
}

/** Two consecutive frames from a real finished drama (scene 1, the MS and its
 * OTS reverse) — the pipeline's output sitting right beside its diagram.
 * They take turns "playing": shot 3 drifts like live footage while its border
 * lights, then shot 4 takes its turn, on a shared 6s cycle. */
function SampleFrames({ reduced }: { reduced: boolean }) {
  const frames = [
    { src: "/sample-shot3.jpg", label: "Shot 3 · MS", delay: "0s" },
    { src: "/sample-shot4.jpg", label: "Shot 4 · OTS", delay: "3s" },
  ];
  return (
    <div className="hidden shrink-0 sm:block">
      <div className="flex gap-2">
        {frames.map((f) => (
          <figure key={f.src} className="w-[92px]">
            <div
              className={cn(
                "overflow-hidden rounded-md border border-white/10",
                !reduced && "animate-[take-glow_6s_ease-in-out_infinite]"
              )}
              style={!reduced ? { animationDelay: f.delay } : undefined}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={f.src}
                alt=""
                loading="lazy"
                className={cn(
                  "aspect-[9/16] w-full object-cover",
                  !reduced && "animate-[take-turn_6s_ease-in-out_infinite]"
                )}
                style={!reduced ? { animationDelay: f.delay } : undefined}
              />
            </div>
            <figcaption className="mt-1 text-center text-[9px] uppercase tracking-widest text-muted-foreground">
              {f.label}
            </figcaption>
          </figure>
        ))}
      </div>
      <p className="mt-1.5 text-center text-[10px] text-muted-foreground">
        straight from a finished drama
      </p>
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

        <GlowCard className="md:col-span-5">
          <CardText {...WOWS[2]} />
          <StyleReel reduced={reduced} />
        </GlowCard>

        <GlowCard className="md:col-span-7">
          <div className="flex gap-5">
            <div className="min-w-0 flex-1">
              <CardText {...WOWS[3]} />
              <TwoDoorsPipeline reduced={reduced} />
            </div>
            <SampleFrames reduced={reduced} />
          </div>
        </GlowCard>

        <GlowCard className="md:col-span-4">
          <CardText {...WOWS[4]} />
          <WardrobeRow />
        </GlowCard>

        <GlowCard className="md:col-span-4">
          <CardText {...WOWS[5]} />
          <SpeechWave reduced={reduced} />
        </GlowCard>

        <GlowCard className="md:col-span-4">
          <CardText {...WOWS[6]} />
          <DirectorTools />
        </GlowCard>
      </div>
    </section>
  );
}
