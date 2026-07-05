"use client";

import { useEffect, useRef, useState } from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { useReducedMotion } from "@/hooks/useReducedMotion";

const WOWS = [
  {
    k: "01",
    title: "One premise, a whole drama",
    body: "An autonomous agent writes the script, judges its own draft, casts the characters, storyboards every scene and reports back. You watch a studio work for you.",
  },
  {
    k: "02",
    title: "Faces that never drift",
    body: "Upload one reference photo. Every clip is verified against a real facial embedding, and weak takes retry themselves until the face holds.",
  },
  {
    k: "03",
    title: "Wardrobe built in",
    body: "Every character gets costume plates for each look in the story, so the same person walks through every scene wearing the right outfit.",
  },
  {
    k: "04",
    title: "Clone your voice",
    body: "Read one short passage into your mic and your characters speak with your voice, or pick from a catalog of studio presets.",
  },
  {
    k: "05",
    title: "You stay the director",
    body: "Edit the script, swap faces, redo plates, delete shots, regenerate clips. The agent runs the pipeline while you keep creative control.",
  },
  {
    k: "06",
    title: "The budget is a feature",
    body: "A live meter spends premium generation only on the shots that matter, turning a hard limit into a smart allocator.",
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
  const frames = ["/poster3.jpg", "/poster6.jpg", "/poster10.jpg", "/poster15.jpg"];
  return (
    <div className="mt-6 flex items-center gap-3">
      <div className="flex shrink-0 flex-col items-center gap-1">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/poster13.jpg"
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

export function FeatureBento() {
  const reduced = useReducedMotion();
  const faces = WOWS[1];
  const budget = WOWS[5];
  const compact = [WOWS[0], WOWS[2], WOWS[3], WOWS[4]];

  return (
    <section id="features" className="mx-auto max-w-6xl px-6 pb-28">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-12">
        <GlowCard className="md:col-span-7">
          <CardText {...faces} />
          <FaceScanStrip reduced={reduced} />
        </GlowCard>

        <GlowCard className="md:col-span-5">
          <CardText {...budget} />
          <BudgetMeterMini reduced={reduced} />
        </GlowCard>

        {compact.map((w) => (
          <GlowCard key={w.k} className="md:col-span-3">
            <CardText {...w} />
          </GlowCard>
        ))}
      </div>
    </section>
  );
}
