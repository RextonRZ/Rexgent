"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface Episode {
  id: string;
  title: string;
  videoSrc: string;
  posterSrc: string;
}

// The five strongest EMBERWAKE shots: establish → mystery → horror → monster → payoff.
const EPISODES: Episode[] = [
  { id: "ep1", title: "The Ember Field", videoSrc: "/clip1.mp4", posterSrc: "/poster1.jpg" },
  { id: "ep2", title: "The Signal", videoSrc: "/clip5.mp4", posterSrc: "/poster5.jpg" },
  { id: "ep3", title: "Don't Open It", videoSrc: "/clip7.mp4", posterSrc: "/poster7.jpg" },
  { id: "ep4", title: "It Wakes", videoSrc: "/clip9.mp4", posterSrc: "/poster9.jpg" },
  { id: "ep5", title: "Emberwake", videoSrc: "/clip12.mp4", posterSrc: "/poster12.jpg" },
];

const ADVANCE_MS = 6000;
const FEED_STEP_MS = 340;
const EASE = "cubic-bezier(0.32, 0.72, 0, 1)";
const SLOT_TRANSITION = `top 600ms ${EASE}, transform 600ms ${EASE}, opacity 600ms ${EASE}`;

// The curve is an illusion: flat frames, per-slot transforms along an S.
// Slot 0 is the featured center; negatives hang above, positives below.
const SLOTS: Record<
  number,
  { top: string; x: number; rx: number; r: number; s: number; o: number; z: number }
> = {
  [-2]: { top: "2%", x: 48, rx: 6, r: 9, s: 0.5, o: 0.4, z: 10 },
  [-1]: { top: "26%", x: 16, rx: 3, r: 4, s: 0.68, o: 0.7, z: 20 },
  [0]: { top: "50%", x: 0, rx: 0, r: -2, s: 1, o: 1, z: 30 },
  [1]: { top: "74%", x: 16, rx: -3, r: -5, s: 0.68, o: 0.7, z: 20 },
  [2]: { top: "98%", x: 48, rx: -6, r: -9, s: 0.5, o: 0.4, z: 10 },
};

// rel 0..4 (distance below featured, circular) → slot -2..+2
const slotOf = (rel: number) => (rel <= 2 ? rel : rel - 5);

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const fn = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, []);
  return reduced;
}

// null until mounted — lets us render exactly one variant (never two videos).
function useIsDesktop() {
  const [val, setVal] = useState<boolean | null>(null);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const fn = () => setVal(mq.matches);
    fn();
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, []);
  return val;
}

/** Vertical film: perforations run down the left and right edges. */
function Sprockets() {
  return (
    <div
      aria-hidden
      className="flex w-6 shrink-0 flex-col items-center justify-center gap-4 py-2"
    >
      {Array.from({ length: 8 }).map((_, i) => (
        <span key={i} className="h-[9px] w-[7px] rounded-[2px] bg-zinc-700" />
      ))}
    </div>
  );
}

/** Only the featured slot mounts this; fades in over the poster once playing. */
function FeaturedVideo({ src }: { src: string }) {
  const ref = useRef<HTMLVideoElement>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    v.play().catch(() => {
      /* muted+playsinline should allow autoplay; poster stays if blocked */
    });
    return () => v.pause();
  }, []);

  return (
    <video
      ref={ref}
      src={src}
      muted
      loop
      playsInline
      autoPlay
      preload="metadata"
      onPlaying={() => setReady(true)}
      className={cn(
        "absolute inset-0 h-full w-full object-cover transition-opacity duration-300",
        ready ? "opacity-100" : "opacity-0"
      )}
    />
  );
}

function FilmFrame({
  ep,
  n,
  featured,
  playing,
  onClick,
  className,
}: {
  ep: Episode;
  n: number;
  featured: boolean;
  playing: boolean;
  onClick?: () => void;
  className?: string;
}) {
  return (
    <div
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => e.key === "Enter" && onClick() : undefined}
      aria-label={onClick ? `Feature EP ${n} · ${ep.title}` : undefined}
      className={cn(
        "flex items-stretch rounded-md border border-zinc-800 bg-zinc-950",
        featured && "shadow-2xl",
        onClick && "cursor-pointer",
        className
      )}
    >
      <Sprockets />
      <div className="relative my-2 min-w-0 flex-1 overflow-hidden rounded-[3px] bg-zinc-900">
        <img
          src={ep.posterSrc}
          alt={`EP ${n} · ${ep.title}`}
          className="aspect-video w-full object-cover"
          draggable={false}
        />
        {playing && <FeaturedVideo key={ep.id} src={ep.videoSrc} />}
        {featured && (
          <>
            <div className="pointer-events-none absolute inset-x-0 bottom-0 h-14 bg-gradient-to-t from-black/70 to-transparent" />
            <div className="absolute bottom-2 left-2 flex items-center gap-1.5 rounded-full bg-black/60 px-2.5 py-1 text-[11px] text-white/90 backdrop-blur-sm">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red-500" />
              <span className="truncate">
                <span className="font-medium text-primary">EP {n}</span> ·{" "}
                {ep.title} — generated by Rexgent
              </span>
            </div>
          </>
        )}
      </div>
      <Sprockets />
    </div>
  );
}

function Pips({
  featured,
  onSelect,
  vertical,
  className,
}: {
  featured: number;
  onSelect: (i: number) => void;
  vertical?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("flex gap-2", vertical ? "flex-col" : "flex-row", className)}>
      {EPISODES.map((ep, i) => (
        <button
          key={ep.id}
          aria-label={`Feature EP ${i + 1} · ${ep.title}`}
          title={`EP ${i + 1} · ${ep.title}`}
          onClick={() => onSelect(i)}
          className={cn(
            "rounded-full transition-all",
            i === featured ? "bg-primary" : "bg-zinc-600 hover:bg-zinc-400",
            vertical
              ? i === featured
                ? "h-5 w-1.5"
                : "h-1.5 w-1.5"
              : i === featured
              ? "h-1.5 w-5"
              : "h-1.5 w-1.5"
          )}
        />
      ))}
    </div>
  );
}

export function FilmstripHero() {
  const reduced = usePrefersReducedMotion();
  const desktop = useIsDesktop();
  const [featured, setFeatured] = useState(0);
  const [target, setTarget] = useState<number | null>(null);
  const [hovered, setHovered] = useState(false);
  const [inView, setInView] = useState(true);
  const [pageVisible, setPageVisible] = useState(true);
  const rootRef = useRef<HTMLDivElement>(null);
  const prevFeaturedRef = useRef(0);
  const touchX = useRef<number | null>(null);

  // Captured before the post-render effect updates it, so during a render we
  // still see the previous featured index — used to spot the wrapping frame.
  const prevFeatured = prevFeaturedRef.current;
  useEffect(() => {
    prevFeaturedRef.current = featured;
  }, [featured]);

  const step = useCallback((dir: 1 | -1 = 1) => {
    setFeatured((f) => (f + dir + EPISODES.length) % EPISODES.length);
  }, []);

  // Clicking a frame feeds the strip one position at a time until it arrives.
  useEffect(() => {
    if (target === null) return;
    if (target === featured) {
      setTarget(null);
      return;
    }
    const t = window.setTimeout(() => step(1), FEED_STEP_MS);
    return () => window.clearTimeout(t);
  }, [target, featured, step]);

  useEffect(() => {
    const onVis = () => setPageVisible(!document.hidden);
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setInView(e.isIntersecting), {
      threshold: 0.15,
    });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  // Auto-advance: paused on hover, hidden tab, off-screen, reduced motion,
  // or while feeding toward a clicked episode.
  useEffect(() => {
    if (reduced || hovered || !inView || !pageVisible || target !== null) return;
    const t = window.setInterval(() => step(1), ADVANCE_MS);
    return () => window.clearInterval(t);
  }, [reduced, hovered, inView, pageVisible, target, step]);

  const feedTo = (i: number) => {
    if (i === featured) return;
    setTarget(i);
    step(1);
  };

  // Reduced motion: static featured poster + manual pips, no tilt, no autoplay.
  if (reduced) {
    return (
      <div
        ref={rootRef}
        className="flex w-full flex-col items-center gap-4 md:justify-center md:self-stretch"
      >
        <FilmFrame
          ep={EPISODES[featured]}
          n={featured + 1}
          featured
          playing={false}
          className="w-full max-w-[480px]"
        />
        <Pips featured={featured} onSelect={setFeatured} />
      </div>
    );
  }

  return (
    <div
      ref={rootRef}
      className="relative w-full md:h-full md:min-h-[560px] md:self-stretch"
    >
      {/* pre-mount placeholder: one static frame, no video, no layout shift */}
      {desktop === null && (
        <div className="flex h-full min-h-[320px] w-full items-center justify-center">
          <FilmFrame
            ep={EPISODES[featured]}
            n={featured + 1}
            featured
            playing={false}
            className="w-full max-w-[440px]"
          />
        </div>
      )}

      {/* desktop: the curved strip, bleeding past the hero's top and bottom */}
      {desktop === true && (
        <>
          <div
            className="absolute inset-0 overflow-hidden [perspective:1200px]"
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
          >
            {EPISODES.map((ep, i) => {
              const rel = (i - featured + EPISODES.length) % EPISODES.length;
              const slot = slotOf(rel);
              const prevSlot = slotOf(
                (i - prevFeatured + EPISODES.length) % EPISODES.length
              );
              // The frame recycling from top to bottom must not animate the
              // full trip through the middle of the strip.
              const wrapping = Math.abs(slot - prevSlot) > 1;
              const s = SLOTS[slot];
              return (
                <div
                  key={ep.id}
                  className="absolute left-1/2 w-[440px] max-w-[85%]"
                  style={{
                    top: s.top,
                    zIndex: s.z,
                    opacity: s.o,
                    transform: `translate(calc(-50% + ${s.x}px), -50%) rotateX(${s.rx}deg) rotate(${s.r}deg) scale(${s.s})`,
                    transition: wrapping ? "none" : SLOT_TRANSITION,
                  }}
                >
                  <FilmFrame
                    ep={ep}
                    n={i + 1}
                    featured={slot === 0}
                    playing={slot === 0}
                    onClick={slot === 0 ? undefined : () => feedTo(i)}
                  />
                </div>
              );
            })}
          </div>
          <Pips
            featured={featured}
            onSelect={feedTo}
            vertical
            className="absolute -left-3 top-1/2 z-40 -translate-y-1/2"
          />
        </>
      )}

      {/* mobile: one full-width featured frame, swipeable */}
      {desktop === false && (
        <div
          className="w-full"
          onTouchStart={(e) => {
            touchX.current = e.touches[0].clientX;
          }}
          onTouchEnd={(e) => {
            const dx = e.changedTouches[0].clientX - (touchX.current ?? 0);
            if (Math.abs(dx) > 40) step(dx < 0 ? 1 : -1);
            touchX.current = null;
          }}
        >
          <FilmFrame
            ep={EPISODES[featured]}
            n={featured + 1}
            featured
            playing
            className="w-full"
          />
          <Pips
            featured={featured}
            onSelect={feedTo}
            className="mt-3 justify-center"
          />
        </div>
      )}
    </div>
  );
}
