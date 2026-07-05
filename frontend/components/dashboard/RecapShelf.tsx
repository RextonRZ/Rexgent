"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { BTN_PRIMARY, CtaArrow } from "@/components/ui/cta";
import { cn } from "@/lib/utils";
import { useReducedMotion } from "@/hooks/useReducedMotion";
import { fmtFilm } from "@/components/dashboard/format";
import type { ProjectsOverview, RecentClip } from "@/lib/types";

// Shown while the studio has no clips of its own yet.
const DEFAULT_REEL: RecentClip[] = [
  { url: "/preview15.mp4", project_id: "", project_title: "Demo reel" },
  { url: "/preview13.mp4", project_id: "", project_title: "Demo reel" },
  { url: "/preview10.mp4", project_id: "", project_title: "Demo reel" },
];

const CYCLE_MS = 3800;
const FADE_MS = 300;

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

/** Counts 0 → target once, the first time a real value arrives. */
function useCountUp(target: number, reduced: boolean): number {
  const [val, setVal] = useState(0);
  const animated = useRef(false);

  useEffect(() => {
    if (reduced || target <= 0 || animated.current) {
      setVal(target);
      return;
    }
    animated.current = true;
    const t0 = performance.now();
    const dur = 1200;
    let raf: number;
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / dur);
      setVal(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, reduced]);

  return val;
}

function ShelfSprockets({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "absolute inset-y-0 z-10 flex flex-col items-center justify-evenly opacity-30",
        className
      )}
    >
      {Array.from({ length: 10 }).map((_, i) => (
        <span key={i} className="h-[7px] w-[6px] rounded-[1px] bg-white/30" />
      ))}
    </div>
  );
}

export function RecapShelf({
  overview,
  userName,
  onNewDrama,
}: {
  overview?: ProjectsOverview;
  userName?: string | null;
  onNewDrama: () => void;
}) {
  const router = useRouter();
  const reduced = useReducedMotion();
  const rootRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [idx, setIdx] = useState(0);
  const [visible, setVisible] = useState(true);
  const [inView, setInView] = useState(true);
  const [pageVisible, setPageVisible] = useState(true);

  const ownClips = overview?.recent_clips ?? [];
  const fallback = ownClips.length === 0;
  const clips = fallback ? DEFAULT_REEL : ownClips;
  const current = clips[idx % clips.length];

  const totals = overview?.totals;
  const dramas = useCountUp(totals?.dramas ?? 0, reduced);
  const clipCount = useCountUp(totals?.clips ?? 0, reduced);
  const filmSecs = useCountUp(totals?.film_seconds ?? 0, reduced);
  const spent = useCountUp(totals?.spent_usd ?? 0, reduced);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setInView(e.isIntersecting), {
      threshold: 0.2,
    });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    const onVis = () => setPageVisible(!document.hidden);
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  const running = inView && pageVisible && !reduced;

  // Montage: dissolve out, advance, dissolve back in.
  useEffect(() => {
    if (!running || clips.length < 2) return;
    const t = window.setInterval(() => {
      setVisible(false);
      window.setTimeout(() => {
        setIdx((i) => (i + 1) % clips.length);
        setVisible(true);
      }, FADE_MS);
    }, CYCLE_MS);
    return () => window.clearInterval(t);
  }, [running, clips.length]);

  // Only-one-video rule: pause whenever the shelf can't be seen.
  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    if (running) v.play().catch(() => {});
    else v.pause();
  }, [running, idx]);

  const openCurrent = () => {
    if (current?.project_id) {
      router.push(`/projects/${current.project_id}/script`);
    } else {
      onNewDrama();
    }
  };

  const staticPoster =
    overview?.projects.find((p) => p.poster_url)?.poster_url ?? "/still12.jpg";

  return (
    <section
      ref={rootRef}
      className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-[#0a0812] px-6 py-8 lg:px-10"
    >
      <div className="grid items-center gap-8 lg:grid-cols-[2fr_3fr]">
        {/* greeting + stats + CTA */}
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {greeting()}
            {userName ? `, ${userName}` : ""}
          </h1>
          <p className="mt-3 text-sm text-muted-foreground">
            <span className="font-semibold text-foreground">
              {Math.round(dramas)}
            </span>{" "}
            dramas ·{" "}
            <span className="font-semibold text-foreground">
              {Math.round(clipCount)}
            </span>{" "}
            clips ·{" "}
            <span className="font-semibold text-foreground">
              {fmtFilm(filmSecs)}
            </span>{" "}
            of film ·{" "}
            <span className="font-semibold text-foreground">
              ${spent.toFixed(2)}
            </span>{" "}
            spent
          </p>
          <Button
            onClick={onNewDrama}
            className={cn(
              "mt-6 h-11",
              BTN_PRIMARY,
              "shadow-[0_0_20px_rgba(139,92,246,0.30)]"
            )}
          >
            Start a new drama
            <CtaArrow />
          </Button>
        </div>

        {/* the screen */}
        <div>
          <button
            onClick={openCurrent}
            aria-label={
              current?.project_id
                ? `Open ${current.project_title}`
                : "Start a new drama"
            }
            className="relative block w-full overflow-hidden rounded-xl border border-zinc-800 bg-black text-left shadow-2xl shadow-black/60 outline-none transition-colors hover:border-zinc-700 focus-visible:ring-2 focus-visible:ring-violet-400/60"
          >
            <div className="relative aspect-video">
              {reduced ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={staticPoster}
                  alt=""
                  className="absolute inset-0 h-full w-full object-cover"
                />
              ) : (
                <video
                  ref={videoRef}
                  key={current?.url}
                  src={current?.url}
                  muted
                  loop
                  playsInline
                  autoPlay
                  preload="metadata"
                  className={cn(
                    "absolute inset-0 h-full w-full object-cover transition-opacity duration-300",
                    visible ? "opacity-100" : "opacity-0"
                  )}
                />
              )}
              <ShelfSprockets className="left-1.5" />
              <ShelfSprockets className="right-1.5" />

              {fallback && (
                <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/40">
                  <p className="rounded-full bg-black/60 px-4 py-1.5 text-sm text-zinc-200 backdrop-blur-sm">
                    Your dramas will play here
                  </p>
                </div>
              )}

              {!reduced && current && !fallback && (
                <div className="absolute bottom-2 left-8 z-10 flex items-center gap-1.5 rounded-full bg-black/60 px-2.5 py-1 text-[11px] text-white/90 backdrop-blur-sm">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red-500" />
                  <span className="truncate">
                    <span className="font-medium text-primary">
                      EP {(idx % clips.length) + 1}
                    </span>{" "}
                    · {current.project_title}
                  </span>
                </div>
              )}
            </div>
          </button>
          {/* floor reflection */}
          <div
            aria-hidden
            className="mx-auto -mt-2 h-10 w-4/5 rounded-[100%] bg-violet-500/10 blur-2xl"
          />
        </div>
      </div>
    </section>
  );
}
