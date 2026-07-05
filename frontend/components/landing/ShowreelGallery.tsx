"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface ReelShot {
  id: string;
  title: string;
  imgSrc: string;
  /** small silent encode the strip plays continuously */
  videoSrc?: string;
  /** full-quality clip for the lightbox */
  fullSrc?: string;
}

// The shots not used in the hero strip — the rest of the reel.
const REEL_SHOTS: ReelShot[] = [
  { id: "s15", title: "Opening Scene", imgSrc: "/poster15.jpg", videoSrc: "/preview15.mp4", fullSrc: "/clip15.mp4" },
  { id: "s13", title: "Morning Light", imgSrc: "/poster13.jpg", videoSrc: "/preview13.mp4", fullSrc: "/clip13.mp4" },
  { id: "s3", title: "The Meeting", imgSrc: "/poster3.jpg", videoSrc: "/preview3.mp4", fullSrc: "/clip3.mp4" },
  { id: "s4", title: "Side by Side", imgSrc: "/poster4.jpg", videoSrc: "/preview4.mp4", fullSrc: "/clip4.mp4" },
  { id: "s6", title: "A Quiet Walk", imgSrc: "/poster6.jpg", videoSrc: "/preview6.mp4", fullSrc: "/clip6.mp4" },
  { id: "s2", title: "City Lights", imgSrc: "/poster2.jpg", videoSrc: "/preview2.mp4", fullSrc: "/clip2.mp4" },
  { id: "s8", title: "The Promise", imgSrc: "/poster8.jpg", videoSrc: "/preview8.mp4", fullSrc: "/clip8.mp4" },
  // s14 is the same footage as s2 — keep them apart even across the loop seam
  { id: "s14", title: "Stars Above", imgSrc: "/poster14.jpg", videoSrc: "/preview14.mp4", fullSrc: "/clip14.mp4" },
  { id: "s10", title: "Golden Hour", imgSrc: "/poster10.jpg", videoSrc: "/preview10.mp4", fullSrc: "/clip10.mp4" },
  { id: "s11", title: "Almost Said", imgSrc: "/poster11.jpg", videoSrc: "/preview11.mp4", fullSrc: "/clip11.mp4" },
];

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

/** Horizontal film: perforations run along the top and bottom edges. */
function SprocketRow() {
  return (
    <div
      aria-hidden
      className="flex justify-center gap-4 overflow-hidden py-1.5"
    >
      {Array.from({ length: 180 }).map((_, i) => (
        <span
          key={i}
          className="h-[9px] w-[7px] shrink-0 rounded-[2px] bg-zinc-700"
        />
      ))}
    </div>
  );
}

/** Every frame plays its clip continuously — but each cell watches its own
 *  viewport intersection, so only the ~handful of frames actually on screen
 *  decode video. The rest sit paused on their poster. */
function CellVideo({
  shot,
  allowed,
}: {
  shot: ReelShot;
  allowed: boolean;
}) {
  const ref = useRef<HTMLVideoElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    const io = new IntersectionObserver(
      ([e]) => setVisible(e.isIntersecting),
      { threshold: 0.05 }
    );
    io.observe(v);
    return () => io.disconnect();
  }, []);

  const playing = allowed && visible;
  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    if (playing) v.play().catch(() => {});
    else v.pause();
  }, [playing]);

  return (
    <video
      ref={ref}
      src={shot.videoSrc}
      poster={shot.imgSrc}
      muted
      loop
      playsInline
      preload="metadata"
      className="aspect-video w-full object-cover"
    />
  );
}

export function ShowreelGallery() {
  const reduced = usePrefersReducedMotion();
  const sectionRef = useRef<HTMLElement>(null);
  const [inView, setInView] = useState(true);
  const [pageVisible, setPageVisible] = useState(true);
  const [lightbox, setLightbox] = useState<ReelShot | null>(null);

  const running = inView && pageVisible;

  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setInView(e.isIntersecting), {
      threshold: 0.1,
    });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    const onVis = () => setPageVisible(!document.hidden);
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  // ESC closes the lightbox
  useEffect(() => {
    if (!lightbox) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLightbox(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [lightbox]);

  const renderCell = (shot: ReelShot, copy: number) => {
    const key = `${shot.id}:${copy}`;
    return (
      <div key={key} className="shrink-0 snap-start pr-3">
        <button
          onClick={() => setLightbox(shot)}
          aria-label={`Watch ${shot.title}`}
          className="relative block w-[280px] max-w-[70vw] overflow-hidden rounded-sm border border-zinc-800 bg-zinc-900 transition-all duration-300 hover:scale-105 hover:brightness-110 focus-visible:ring-2 focus-visible:ring-violet-400/60 outline-none"
        >
          {shot.videoSrc ? (
            <CellVideo shot={shot} allowed={running && !reduced} />
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={shot.imgSrc}
              alt={shot.title}
              loading="lazy"
              draggable={false}
              className="aspect-video w-full object-cover"
            />
          )}
        </button>
      </div>
    );
  };

  // Each strip is one continuous piece of film: sprockets top and bottom,
  // frames exposed in between. The marquee track holds two copies of the
  // shot list so translateX(-50%) loops seamlessly.
  const renderStrip = (
    shots: ReelShot[],
    direction: "left" | "right",
    tilt: string
  ) => (
    <div
      className={cn(
        "group relative w-[104vw] -ml-[2vw] border-y border-zinc-800 bg-zinc-950",
        tilt
      )}
    >
      <SprocketRow />
      <div className="overflow-hidden">
        {reduced ? (
          <div className="flex snap-x snap-mandatory overflow-x-auto px-6">
            {shots.map((s) => renderCell(s, 0))}
          </div>
        ) : (
          <div
            className={cn(
              "flex w-max",
              direction === "left"
                ? "animate-[reel-left_40s_linear_infinite]"
                : "animate-[reel-right_40s_linear_infinite]",
              "group-hover:[animation-play-state:paused]",
              !running && "[animation-play-state:paused]"
            )}
          >
            {shots.map((s) => renderCell(s, 0))}
            {shots.map((s) => renderCell(s, 1))}
          </div>
        )}
      </div>
      <SprocketRow />
    </div>
  );

  const half = Math.ceil(REEL_SHOTS.length / 2);
  const stripA = REEL_SHOTS.slice(0, half);
  const stripB = REEL_SHOTS.slice(half);

  return (
    <section id="reel" ref={sectionRef} className="overflow-hidden pb-24">
      <div className="mb-10 px-6 text-center">
        <p className="text-xs uppercase tracking-[0.3em] text-primary/80 mb-2">
          Every shot generated, not filmed
        </p>
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">
          A reel that didn&apos;t exist this morning
        </h2>
      </div>

      <div className="space-y-8 py-4">
        {renderStrip(stripA, "left", "-rotate-1")}
        {renderStrip(stripB, "right", "rotate-1")}
      </div>

      {/* minimal lightbox */}
      {lightbox && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6 backdrop-blur-sm"
          onClick={() => setLightbox(null)}
        >
          <button
            aria-label="Close"
            onClick={() => setLightbox(null)}
            className="absolute right-6 top-5 text-zinc-400 transition-colors hover:text-white"
          >
            <X className="size-6" />
          </button>
          <div
            className="flex flex-col items-center gap-3"
            onClick={(e) => e.stopPropagation()}
          >
            {lightbox.fullSrc || lightbox.videoSrc ? (
              <video
                src={lightbox.fullSrc ?? lightbox.videoSrc}
                autoPlay
                loop
                muted
                playsInline
                controls
                className="max-h-[78vh] max-w-[92vw] rounded-lg border border-zinc-800"
              />
            ) : (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={lightbox.imgSrc}
                alt={lightbox.title}
                className="max-h-[78vh] max-w-[92vw] rounded-lg border border-zinc-800"
              />
            )}
            <p className="text-sm text-zinc-300">{lightbox.title}</p>
          </div>
        </div>
      )}
    </section>
  );
}
