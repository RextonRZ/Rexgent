"use client";

import { useEffect, useRef } from "react";

// The shots not used in the hero — the rest of the EMBERWAKE reel.
const REEL_CLIPS = [
  "/clip15.mp4",
  "/clip13.mp4",
  "/clip3.mp4",
  "/clip4.mp4",
  "/clip6.mp4",
  "/clip2.mp4",
  "/clip8.mp4",
  "/clip10.mp4",
];

/** A muted loop that only downloads + plays while it's on screen. */
function ShowreelClip({ src }: { src: string }) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.play().catch(() => {});
        } else {
          el.pause();
        }
      },
      { threshold: 0.25 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <video
      ref={ref}
      src={src}
      muted
      loop
      playsInline
      preload="none"
      className="aspect-video w-full rounded-xl border hairline object-cover transition-transform duration-300 hover:scale-[1.02]"
    />
  );
}

export function ShowreelGallery() {
  return (
    <section className="mx-auto max-w-6xl px-6 pb-24">
      <div className="mb-6 text-center">
        <p className="text-xs uppercase tracking-[0.3em] text-primary/80 mb-2">
          Every shot generated, not filmed
        </p>
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">
          A reel that didn&apos;t exist this morning
        </h2>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {REEL_CLIPS.map((src) => (
          <ShowreelClip key={src} src={src} />
        ))}
      </div>
    </section>
  );
}
