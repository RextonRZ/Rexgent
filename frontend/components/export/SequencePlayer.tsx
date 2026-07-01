"use client";

import { useEffect, useRef, useState } from "react";

export interface TimelineItem {
  clipId: string;
  shotId: string;
  url: string;
  label: string;
  score: number | null;
}

/** Plays the timeline clips back-to-back, like a preview of the final cut. */
export function SequencePlayer({
  items,
  index,
  onIndexChange,
}: {
  items: TimelineItem[];
  index: number;
  onIndexChange: (i: number) => void;
}) {
  const ref = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);

  const safeIndex = Math.min(index, Math.max(0, items.length - 1));
  const current = items[safeIndex];

  // Load the current clip whenever the index (or its url) changes.
  useEffect(() => {
    const v = ref.current;
    if (!v || !current) return;
    v.load();
    if (playing) v.play().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [safeIndex, current?.url]);

  const handleEnded = () => {
    if (safeIndex < items.length - 1) {
      onIndexChange(safeIndex + 1);
    } else {
      setPlaying(false);
    }
  };

  const togglePlay = () => {
    const v = ref.current;
    if (!v) return;
    if (playing) {
      v.pause();
      setPlaying(false);
    } else {
      v.play().catch(() => {});
      setPlaying(true);
    }
  };

  if (!current) {
    return (
      <div className="aspect-video w-full rounded-2xl border hairline bg-black/60 flex items-center justify-center text-sm text-muted-foreground">
        Add clips to the timeline to preview your cut.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="relative aspect-video w-full overflow-hidden rounded-2xl border hairline bg-black">
        <video
          ref={ref}
          className="h-full w-full object-contain"
          onEnded={handleEnded}
          onClick={togglePlay}
          playsInline
        >
          <source src={current.url} type="video/mp4" />
        </video>

        {!playing && (
          <button
            onClick={togglePlay}
            className="absolute inset-0 flex items-center justify-center bg-black/20 hover:bg-black/30 transition-colors"
          >
            <span className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/90 text-white text-xl glow">
              ▶
            </span>
          </button>
        )}

        <div className="absolute top-3 left-3 rounded-full bg-black/50 px-2.5 py-1 text-[11px] text-white/90 backdrop-blur-sm">
          Now: {current.label} · clip {safeIndex + 1}/{items.length}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={togglePlay}
          className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground glow"
        >
          {playing ? "❚❚ Pause" : "▶ Play cut"}
        </button>
        <span className="text-xs text-muted-foreground">
          {items.length} clip{items.length === 1 ? "" : "s"} · plays in timeline
          order
        </span>
      </div>
    </div>
  );
}
