"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { BarChart3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { BTN_PRIMARY, CtaArrow } from "@/components/ui/cta";
import { GRAIN } from "@/components/landing/CtaBackdrop";
import { StudioStatsDrawer } from "@/components/dashboard/StudioStats";
import { PosterImage, statusOf } from "@/components/dashboard/ProjectCards";
import { cn } from "@/lib/utils";
import { useReducedMotion } from "@/hooks/useReducedMotion";
import { useCountUp } from "@/hooks/useCountUp";
import { fmtFilm, relTime } from "@/components/dashboard/format";
import type { ProjectsOverview } from "@/lib/types";

const CYCLE_MS = 3800;
const FADE_MS = 300;

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

/** Vertical film perforations down one edge — matches the landing FilmstripHero. */
function Sprockets() {
  return (
    <div
      aria-hidden
      className="flex w-6 shrink-0 flex-col items-center justify-center gap-4 py-2"
    >
      {Array.from({ length: 9 }).map((_, i) => (
        <span key={i} className="h-[9px] w-[7px] rounded-[2px] bg-zinc-700" />
      ))}
    </div>
  );
}

/** Vintage countdown leader for studios with no footage yet. */
function PremiereAwaits({ reduced }: { reduced: boolean }) {
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-[#050308]">
      {/* projector cone from above */}
      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(80% 60% at 50% -10%, rgba(167,139,250,0.08), transparent 60%)",
        }}
      />
      {/* live film grain */}
      <div
        aria-hidden
        className={cn(
          "absolute inset-0 opacity-[0.05] mix-blend-overlay",
          !reduced && "animate-[film-grain_0.8s_steps(1)_infinite]"
        )}
        style={{ backgroundImage: GRAIN }}
      />

      {/* countdown leader: two rings, a sweeping hand, 3 → 2 → 1 */}
      <div className="relative flex h-24 w-24 items-center justify-center">
        <div className="absolute inset-0 rounded-full border border-white/15" />
        <div className="absolute inset-2 rounded-full border border-white/10" />
        {!reduced && (
          <div className="absolute inset-0 animate-[leader-hand_2s_linear_infinite]">
            <span className="absolute left-1/2 top-1/2 h-[46%] w-px origin-top bg-white/25" />
          </div>
        )}
        {reduced ? (
          <span className="text-4xl font-bold text-white/50">3</span>
        ) : (
          ["3", "2", "1"].map((n, i) => (
            <span
              key={n}
              className="absolute text-4xl font-bold text-white/50 opacity-0 animate-[leader-num_6s_linear_infinite]"
              style={{ animationDelay: `${i * 2}s` }}
            >
              {n}
            </span>
          ))
        )}
      </div>

      <div className="relative text-center">
        <p className="text-lg font-semibold">Your premiere awaits</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Finish generating a drama and its clips will play here.
        </p>
      </div>
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
  const [statsOpen, setStatsOpen] = useState(false);

  const clips = overview?.recent_clips ?? [];
  const hasClips = clips.length > 0;
  const current = hasClips ? clips[idx % clips.length] : null;

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

  // Never show a zero stat; an empty studio reads as an invitation instead.
  const statParts: React.ReactNode[] = [];
  if ((totals?.dramas ?? 0) > 0)
    statParts.push(
      <span key="d">
        <span className="font-semibold text-foreground">{Math.round(dramas)}</span>{" "}
        dramas
      </span>
    );
  if ((totals?.clips ?? 0) > 0)
    statParts.push(
      <span key="c">
        <span className="font-semibold text-foreground">
          {Math.round(clipCount)}
        </span>{" "}
        clips
      </span>
    );
  if ((totals?.film_seconds ?? 0) > 0)
    statParts.push(
      <span key="f">
        <span className="font-semibold text-foreground">{fmtFilm(filmSecs)}</span>{" "}
        of film
      </span>
    );
  if ((totals?.spent_usd ?? 0) > 0)
    statParts.push(
      <span key="s">
        <span className="font-semibold text-foreground">
          ${spent.toFixed(2)}
        </span>{" "}
        spent
      </span>
    );

  const staticPoster =
    overview?.projects.find((p) => p.poster_url)?.poster_url ?? "/still12.jpg";

  const screenInner = (
    // exact FilmstripHero film frame: sprockets down both edges, video inset
    <div className="flex items-stretch">
      <Sprockets />
      <div className="relative my-2 min-w-0 flex-1 overflow-hidden rounded-[3px] bg-zinc-900">
        <div className="relative aspect-video">
          {hasClips ? (
            reduced ? (
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
            )
          ) : (
            <PremiereAwaits reduced={reduced} />
          )}

          {!reduced && current && (
            <>
              <div className="pointer-events-none absolute inset-x-0 bottom-0 h-14 bg-gradient-to-t from-black/70 to-transparent" />
              <div className="absolute bottom-2 left-2 z-10 flex items-center gap-1.5 rounded-full bg-black/60 px-2.5 py-1 text-[11px] text-white/90 backdrop-blur-sm">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red-500" />
                <span className="truncate">
                  <span className="font-medium text-primary">
                    EP {(idx % clips.length) + 1}
                  </span>{" "}
                  · {current.project_title}
                </span>
              </div>
            </>
          )}
        </div>
      </div>
      <Sprockets />
    </div>
  );

  const screenChrome =
    "relative block w-full rounded-md border border-zinc-800 bg-zinc-950 text-left shadow-2xl shadow-black/60";

  return (
    <section
      ref={rootRef}
      className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-[#0a0812] px-6 py-7 lg:px-10"
    >
      <div className="grid items-center gap-8 lg:grid-cols-[1fr_1fr]">
        {/* greeting + stats + CTA */}
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {greeting()}
            {userName ? `, ${userName}` : ""}
          </h1>
          <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
            {statParts.length > 0 ? (
              statParts.map((part, i) => (
                <span key={i} className="flex items-center gap-2">
                  {i > 0 && <span className="text-zinc-600">·</span>}
                  {part}
                </span>
              ))
            ) : (
              <span>Your studio is ready for its first drama.</span>
            )}
            <button
              onClick={() => setStatsOpen(true)}
              className="ml-1 flex items-center gap-1.5 rounded-lg border border-white/10 px-2.5 py-1 text-xs text-zinc-400 transition-colors hover:border-white/25 hover:text-zinc-200"
            >
              <BarChart3 className="size-3.5" />
              Studio stats
            </button>
          </div>
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

          {/* jump back in: the most recently edited dramas */}
          {(overview?.projects.length ?? 0) > 0 && (
            <div className="mt-6">
              <p className="text-[11px] uppercase tracking-widest text-muted-foreground">
                Jump back in
              </p>
              <div className="mt-2 space-y-1">
                {overview!.projects.slice(0, 3).map((p) => {
                  const s = statusOf(p);
                  return (
                    <button
                      key={p.id}
                      onClick={() => router.push(`/projects/${p.id}/script`)}
                      className="flex w-full items-center gap-3 rounded-lg p-1.5 pr-2 text-left outline-none transition-colors hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-violet-400/60"
                    >
                      <span className="h-10 w-[71px] shrink-0 overflow-hidden rounded-md bg-zinc-950">
                        <PosterImage project={p} />
                      </span>
                      <span className="min-w-0 flex-1 truncate text-sm">
                        {p.title}
                      </span>
                      <span
                        aria-label={s}
                        className={cn(
                          "h-1.5 w-1.5 shrink-0 rounded-full",
                          s === "generating"
                            ? "animate-pulse bg-violet-400"
                            : s === "complete"
                            ? "bg-emerald-400"
                            : "bg-zinc-500"
                        )}
                      />
                      <span className="shrink-0 text-[11px] text-muted-foreground">
                        {relTime(p.updated_at)}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* the screen */}
        <div>
          {hasClips ? (
            <button
              onClick={() =>
                current?.project_id &&
                router.push(`/projects/${current.project_id}/script`)
              }
              aria-label={`Open ${current?.project_title}`}
              className={cn(
                screenChrome,
                "outline-none transition-colors hover:border-zinc-700 focus-visible:ring-2 focus-visible:ring-violet-400/60"
              )}
            >
              {screenInner}
            </button>
          ) : (
            <div className={screenChrome}>{screenInner}</div>
          )}
          {/* floor reflection */}
          <div
            aria-hidden
            className="mx-auto -mt-2 h-10 w-4/5 rounded-[100%] bg-violet-500/10 blur-2xl"
          />
        </div>
      </div>

      <StudioStatsDrawer open={statsOpen} onOpenChange={setStatsOpen} />
    </section>
  );
}
