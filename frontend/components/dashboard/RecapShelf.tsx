"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronLeft, ChevronRight, Play } from "lucide-react";
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

const CLIP_MS = 5000; // per clip on the montage
const STILL_MS = 8000; // per poster still (matches the Ken Burns drift)
const FADE_MS = 500;

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

/** One thing the screen can show: a clip (video) or a poster still (img). */
interface Slide {
  id: string;
  title: string;
  video?: string;
  img?: string;
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

/** Tiny perforation strip inside a jump-back-in thumbnail. */
function ThumbSprockets() {
  return (
    <span
      aria-hidden
      className="absolute inset-y-0.5 left-0.5 z-10 flex flex-col items-center justify-evenly opacity-50"
    >
      {[0, 1, 2].map((i) => (
        <span key={i} className="h-[3px] w-[3px] rounded-[1px] bg-white/70" />
      ))}
    </span>
  );
}

/** Vintage countdown leader for studios with no footage or posters yet. */
function PremiereAwaits({ reduced }: { reduced: boolean }) {
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-[#050308]">
      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(80% 60% at 50% -10%, rgba(167,139,250,0.08), transparent 60%)",
        }}
      />
      <div
        aria-hidden
        className={cn(
          "absolute inset-0 opacity-[0.05] mix-blend-overlay",
          !reduced && "animate-[film-grain_0.8s_steps(1)_infinite]"
        )}
        style={{ backgroundImage: GRAIN }}
      />
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
  // EP 1's framing sits lower than the rest, so only the first slide slides
  // its crop window up to face height; every other slide keeps the house 30%
  const focusForSlide = (slideIndex: number): string =>
    slideIndex === 0 ? "50% 12%" : "50% 30%";

  // What the screen can play: real clips first; expired/absent clips fall
  // back to recent poster stills with a slow Ken Burns drift — never a dead
  // still, never a broken player.
  const clips = overview?.recent_clips ?? [];
  const slides: Slide[] =
    clips.length > 0
      ? clips.map((c) => ({
          id: c.project_id,
          title: c.project_title,
          video: c.url,
        }))
      : (overview?.projects ?? [])
          .filter((p) => p.poster_url)
          .slice(0, 6)
          .map((p) => ({ id: p.id, title: p.title, img: p.poster_url! }));
  const isClips = clips.length > 0;
  const cycleMs = isClips ? CLIP_MS : STILL_MS;
  const current = slides.length > 0 ? slides[idx % slides.length] : null;

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
    if (!running || slides.length < 2) return;
    const t = window.setInterval(() => {
      setVisible(false);
      window.setTimeout(() => {
        setIdx((i) => (i + 1) % slides.length);
        setVisible(true);
      }, FADE_MS);
    }, cycleMs);
    return () => window.clearInterval(t);
  }, [running, slides.length, cycleMs]);

  // Only-one-video rule: pause whenever the shelf can't be seen.
  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    if (running) v.play().catch(() => {});
    else v.pause();
  }, [running, idx]);

  const flip = (dir: 1 | -1) => {
    if (slides.length < 2) return;
    setIdx((i) => (i + dir + slides.length) % slides.length);
    setVisible(true);
  };

  // Never show a zero stat; an empty studio reads as an invitation instead.
  const statParts: React.ReactNode[] = [];
  if ((totals?.dramas ?? 0) > 0)
    statParts.push(
      <span key="d">
        <span className="font-medium text-zinc-200">{Math.round(dramas)}</span>{" "}
        dramas
      </span>
    );
  if ((totals?.clips ?? 0) > 0)
    statParts.push(
      <span key="c">
        <span className="font-medium text-zinc-200">
          {Math.round(clipCount)}
        </span>{" "}
        clips
      </span>
    );
  if ((totals?.film_seconds ?? 0) > 0)
    statParts.push(
      <span key="f">
        <span className="font-medium text-zinc-200">{fmtFilm(filmSecs)}</span>{" "}
        of film
      </span>
    );
  if ((totals?.spent_usd ?? 0) > 0)
    statParts.push(
      <span key="s">
        <span className="font-medium text-zinc-200">${spent.toFixed(2)}</span>{" "}
        spent
      </span>
    );

  const screenInner = (
    // exact FilmstripHero film frame: sprockets down both edges, media inset
    <div className="flex items-stretch">
      <Sprockets />
      <div className="relative my-2 min-w-0 flex-1 overflow-hidden rounded-[3px] bg-zinc-900">
        <div className="relative aspect-video">
          {current ? (
            current.video && !reduced ? (
              <video
                ref={videoRef}
                key={current.video}
                src={current.video}
                muted
                loop
                playsInline
                autoPlay
                preload="metadata"
                style={{ objectPosition: focusForSlide(idx % slides.length) }}
                className={cn(
                  "absolute inset-0 h-full w-full object-cover transition-opacity duration-500",
                  visible ? "opacity-100" : "opacity-0"
                )}
              />
            ) : (
              // poster still — slow Ken Burns drift keeps the screen alive
              // eslint-disable-next-line @next/next/no-img-element
              <img
                key={`${current.img ?? current.id}-${idx}`}
                src={current.img ?? "/still12.jpg"}
                alt=""
                style={{ objectPosition: focusForSlide(idx % slides.length) }}
                className={cn(
                  "absolute inset-0 h-full w-full object-cover transition-opacity duration-500",
                  visible ? "opacity-100" : "opacity-0",
                  !reduced && !current.video &&
                    "animate-[ken-burns_8s_ease-out_forwards]"
                )}
              />
            )
          ) : (
            <PremiereAwaits reduced={reduced} />
          )}

          {current && (
            <>
              {/* hover: a quiet play affordance over the footage */}
              <span
                aria-hidden
                className="pointer-events-none absolute inset-0 z-[5] flex items-center justify-center opacity-0 transition-opacity duration-300 group-hover:opacity-100"
              >
                <span className="flex h-12 w-12 items-center justify-center rounded-full border border-white/20 bg-black/50 backdrop-blur-sm">
                  <Play className="size-5 translate-x-[1px] text-white/90" />
                </span>
              </span>

              <div className="pointer-events-none absolute inset-x-0 bottom-0 h-14 bg-gradient-to-t from-black/70 to-transparent" />
              <div className="absolute bottom-2.5 left-2 z-10 flex items-center gap-1.5 rounded-full bg-black/60 px-2.5 py-1 text-[11px] text-white/90 backdrop-blur-sm">
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full bg-red-500",
                    !reduced && "animate-pulse"
                  )}
                />
                <span className="truncate">
                  <span className="font-medium text-primary">
                    EP {(idx % slides.length) + 1}
                  </span>{" "}
                  · {current.title}
                </span>
              </div>

              {/* manual flip, revealed on hover */}
              {slides.length > 1 && (
                <span className="absolute bottom-2.5 right-2 z-10 flex gap-1 opacity-0 transition-opacity duration-200 focus-within:opacity-100 group-hover:opacity-100">
                  <button
                    aria-label="Previous clip"
                    onClick={(e) => {
                      e.stopPropagation();
                      flip(-1);
                    }}
                    className="flex h-6 w-6 items-center justify-center rounded-full bg-black/60 text-zinc-300 backdrop-blur-sm transition-colors hover:bg-black/80 hover:text-white"
                  >
                    <ChevronLeft className="size-3.5" />
                  </button>
                  <button
                    aria-label="Next clip"
                    onClick={(e) => {
                      e.stopPropagation();
                      flip(1);
                    }}
                    className="flex h-6 w-6 items-center justify-center rounded-full bg-black/60 text-zinc-300 backdrop-blur-sm transition-colors hover:bg-black/80 hover:text-white"
                  >
                    <ChevronRight className="size-3.5" />
                  </button>
                </span>
              )}

              {/* now-playing bar along the bottom bezel */}
              <span className="absolute inset-x-0 bottom-0 z-10 h-[3px] bg-white/10">
                {reduced ? (
                  <span className="block h-full w-1/3 bg-violet-400/70" />
                ) : (
                  <span
                    key={idx}
                    className="block h-full bg-violet-400/80"
                    style={{
                      animation: running
                        ? `screen-progress ${cycleMs}ms linear forwards`
                        : undefined,
                    }}
                  />
                )}
              </span>
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
      className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-[#0a0812] px-7 py-9 lg:px-12 lg:py-10"
    >
      {/* screening-room atmosphere: projector beam from above, live grain,
          corner vignette — the landing CTA's layers at whisper opacity */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div
          className={cn(
            "absolute inset-0",
            !reduced && "animate-[projector-flutter_7s_linear_infinite]"
          )}
          style={{
            background:
              "radial-gradient(110% 80% at 50% -20%, rgba(167,139,250,0.09), transparent 55%)",
          }}
        />
        <div
          className={cn(
            "absolute inset-0 opacity-[0.04] mix-blend-overlay",
            !reduced && "animate-[film-grain_0.8s_steps(1)_infinite]"
          )}
          style={{ backgroundImage: GRAIN }}
        />
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(130% 120% at 50% 40%, transparent 60%, rgba(0,0,0,0.35) 100%)",
          }}
        />
      </div>

      <div className="relative grid items-center gap-10 lg:grid-cols-[2fr_3fr]">
        {/* ── the "you" zone ─────────────────────────────────────────── */}
        <div>
          <h1 className="text-3xl font-medium tracking-tight text-white lg:text-4xl">
            {greeting()}
            {userName ? `, ${userName}` : ""}
          </h1>

          <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-zinc-500">
            {statParts.length > 0 ? (
              statParts.map((part, i) => (
                <span key={i} className="flex items-center gap-2">
                  {i > 0 && <span className="text-zinc-700">·</span>}
                  {part}
                </span>
              ))
            ) : (
              <span>Your studio is ready for its first drama.</span>
            )}
            {statParts.length > 0 && <span className="text-zinc-700">·</span>}
            <button
              onClick={() => setStatsOpen(true)}
              className="underline decoration-zinc-700 underline-offset-4 transition-colors hover:text-zinc-300 hover:decoration-zinc-500"
            >
              Studio stats
            </button>
          </p>

          <Button
            onClick={onNewDrama}
            className={cn(
              "mt-7 h-11",
              BTN_PRIMARY,
              "shadow-[0_0_20px_rgba(139,92,246,0.30)]"
            )}
          >
            Start a new drama
            <CtaArrow />
          </Button>

          {/* jump back in: grouped module of mini film frames */}
          {(overview?.projects.length ?? 0) > 0 && (
            <div className="mt-9">
              <div className="flex items-center gap-3">
                <p className="text-[10px] uppercase tracking-[0.25em] text-zinc-500">
                  Jump back in
                </p>
                <span className="h-px flex-1 bg-white/[0.07]" />
              </div>
              <div className="mt-3 space-y-0.5 rounded-xl bg-white/[0.02] p-1.5">
                {overview!.projects.slice(0, 3).map((p) => {
                  const s = statusOf(p);
                  return (
                    <button
                      key={p.id}
                      onClick={() => router.push(`/projects/${p.id}/script`)}
                      className="group/row relative flex w-full items-center gap-3 overflow-hidden rounded-lg p-1.5 pr-2 text-left outline-none transition-colors hover:bg-white/[0.04] focus-visible:ring-2 focus-visible:ring-violet-400/60"
                    >
                      {/* light wipe across the row on hover */}
                      {!reduced && (
                        <span
                          aria-hidden
                          className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/[0.05] to-transparent transition-transform duration-700 group-hover/row:translate-x-full"
                        />
                      )}
                      <span className="relative h-10 w-[71px] shrink-0 overflow-hidden rounded-md bg-zinc-950">
                        <ThumbSprockets />
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

        {/* ── the screen ─────────────────────────────────────────────── */}
        <div>
          {current ? (
            <div
              role="button"
              tabIndex={0}
              onClick={() => router.push(`/projects/${current.id}/script`)}
              onKeyDown={(e) =>
                e.key === "Enter" && router.push(`/projects/${current.id}/script`)
              }
              aria-label={`Open ${current.title}`}
              className={cn(
                screenChrome,
                "group cursor-pointer outline-none transition-all duration-500 hover:border-zinc-700 focus-visible:ring-2 focus-visible:ring-violet-400/60",
                // the screen glows while footage is rolling; a touch more on hover
                running &&
                  "border-violet-500/20 shadow-[0_0_60px_-12px_rgba(139,92,246,0.45)] hover:shadow-[0_0_70px_-10px_rgba(139,92,246,0.6)]"
              )}
            >
              {screenInner}
            </div>
          ) : (
            <div className={cn(screenChrome, "group")}>{screenInner}</div>
          )}
          {/* floor reflection, brighter while the screen is lit */}
          <div
            aria-hidden
            className={cn(
              "mx-auto -mt-2 h-10 w-4/5 rounded-[100%] blur-2xl transition-colors duration-500",
              current && running ? "bg-violet-500/20" : "bg-violet-500/10"
            )}
          />
        </div>
      </div>

      <StudioStatsDrawer open={statsOpen} onOpenChange={setStatsOpen} />
    </section>
  );
}
