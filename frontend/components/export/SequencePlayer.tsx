"use client";

import { useEffect, useRef, useState } from "react";
import { LoadingVideo } from "@/components/shared/LoadingVideo";

export interface TimelineItem {
  clipId: string; // generated clip id, or a synthetic id for imported media
  shotId: string;
  url: string;
  label: string;
  score: number | null;
  duration: number; // seconds (defaults to 5 until metadata loads)
  trimStart: number;
  trimEnd: number;
  trimmed: boolean;
  external?: boolean; // imported media (not a generated clip)
}

/** A placed voice line from the export's own placement math. */
export interface PreviewSegment {
  start: number;
  duration: number;
  text?: string | null;
  character?: string | null;
  audio_url?: string | null;
}

/** Plays the timeline clips back-to-back, respecting each clip's trim.
 * The frame follows the drama's delivery format (vertical phone frame by
 * default; widescreen when the drama was created 16:9). */
export function SequencePlayer({
  items,
  index,
  onIndexChange,
  onDuration,
  onProgress,
  ratio = "9:16",
  segments,
  chunkAudio,
}: {
  items: TimelineItem[];
  index: number;
  onIndexChange: (i: number) => void;
  onDuration?: (index: number, seconds: number) => void;
  onProgress?: (index: number, currentTime: number) => void;
  ratio?: "9:16" | "16:9";
  /** placed voice lines: the preview shows captions and plays the real TTS
   * audio at the exact times the export will use */
  segments?: PreviewSegment[];
  /** the export's per-chunk audio verdicts, aligned with items: muted fake
   * speech stays silent here too, kept beds play at their bed volume */
  chunkAudio?: { mute: boolean; volume: number | null }[];
}) {
  const frameClass =
    ratio === "16:9"
      ? "relative aspect-video w-full overflow-hidden rounded-2xl border hairline bg-black"
      : "relative mx-auto aspect-[9/16] w-full max-w-[360px] overflow-hidden rounded-2xl border hairline bg-black";
  const ref = useRef<HTMLVideoElement>(null);
  const voiceRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [activeSeg, setActiveSeg] = useState<PreviewSegment | null>(null);

  const safeIndex = Math.min(index, Math.max(0, items.length - 1));
  const current = items[safeIndex];

  // global start (seconds) of each timeline item — the segment clock
  const prefix: number[] = [];
  {
    let acc = 0;
    for (const it of items) {
      prefix.push(acc);
      acc += Math.max(0, it.trimEnd - it.trimStart);
    }
  }

  /** Keep caption + voice in sync with the global playhead. */
  const syncSegments = (globalTime: number, isPlaying: boolean) => {
    const seg =
      segments?.find(
        (s) =>
          s.text &&
          globalTime >= s.start &&
          globalTime < s.start + Math.max(0.5, s.duration)
      ) ?? null;
    if (seg !== activeSeg) setActiveSeg(seg);

    // the real TTS voice, scheduled at its placed time
    if (!voiceRef.current) voiceRef.current = new Audio();
    const voice = voiceRef.current;
    if (seg?.audio_url && isPlaying) {
      const offset = globalTime - seg.start;
      if (!voice.src.includes(seg.audio_url)) {
        voice.src = seg.audio_url;
        voice.currentTime = Math.max(0, offset);
        voice.play().catch(() => {});
      } else if (Math.abs(voice.currentTime - offset) > 0.4) {
        voice.currentTime = Math.max(0, offset);
      }
      if (voice.paused) voice.play().catch(() => {});
    } else if (!voice.paused) {
      voice.pause();
    }
    // the clip's own audio obeys the export's stored verdict: muted fake
    // speech stays silent, a kept bed plays at bed volume — and either way
    // it ducks under an active voice exactly like the real mix
    const v = ref.current;
    if (v) {
      const policy = chunkAudio?.[safeIndex];
      const base = policy?.mute ? 0 : policy?.volume ?? 1.0;
      v.volume = Math.max(
        0,
        Math.min(1, seg?.audio_url && isPlaying ? base * 0.35 : base)
      );
    }
  };

  // Load the current clip whenever the index (or its url) changes, seeking to
  // its in-point once metadata is ready.
  useEffect(() => {
    const v = ref.current;
    if (!v || !current) return;
    v.load();
    const onMeta = () => {
      v.currentTime = current.trimStart || 0;
      onDuration?.(safeIndex, v.duration);
      // apply the chunk's audio verdict before the first frame plays, so a
      // muted fake-speech clip never blurts before timeupdate catches it
      const policy = chunkAudio?.[safeIndex];
      v.volume = policy?.mute ? 0 : Math.max(0, Math.min(1, policy?.volume ?? 1.0));
      if (playing) v.play().catch(() => {});
    };
    v.addEventListener("loadedmetadata", onMeta, { once: true });
    return () => v.removeEventListener("loadedmetadata", onMeta);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [safeIndex, current?.url]);

  const handleEnded = () => {
    if (safeIndex < items.length - 1) {
      onIndexChange(safeIndex + 1);
    } else {
      setPlaying(false);
      voiceRef.current?.pause();
      setActiveSeg(null);
    }
  };

  const handleTimeUpdate = (e: React.SyntheticEvent<HTMLVideoElement>) => {
    const t = e.currentTarget.currentTime;
    onProgress?.(safeIndex, t);
    if (current) {
      syncSegments(prefix[safeIndex] + (t - (current.trimStart || 0)), playing);
      if (t >= current.trimEnd) handleEnded();
    }
  };

  const togglePlay = () => {
    const v = ref.current;
    if (!v) return;
    if (playing) {
      v.pause();
      voiceRef.current?.pause();
      setPlaying(false);
    } else {
      v.play().catch(() => {});
      setPlaying(true);
    }
  };

  if (!current) {
    return (
      <div
        className={
          ratio === "16:9"
            ? "aspect-video w-full rounded-2xl border hairline bg-black/60 flex items-center justify-center text-sm text-muted-foreground"
            : "mx-auto aspect-[9/16] w-full max-w-[360px] rounded-2xl border hairline bg-black/60 flex items-center justify-center px-6 text-center text-sm text-muted-foreground"
        }
      >
        Add clips to the timeline to preview your cut.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* the episode plays the way it ships */}
      <div className={frameClass}>
        <LoadingVideo
          key={current.url}
          ref={ref}
          fit="contain"
          className="h-full w-full"
          onEnded={handleEnded}
          onTimeUpdate={handleTimeUpdate}
          onClick={togglePlay}
          playsInline
        >
          <source src={current.url} type="video/mp4" />
        </LoadingVideo>

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

        {/* live caption, styled like the burned one and timed identically */}
        {activeSeg?.text && (
          <div className="pointer-events-none absolute inset-x-4 bottom-[14%] text-center">
            <span
              className="inline-block text-[15px] font-bold leading-snug text-white"
              style={{
                textShadow:
                  "-1.5px -1.5px 0 #000, 1.5px -1.5px 0 #000, -1.5px 1.5px 0 #000, 1.5px 1.5px 0 #000",
              }}
            >
              {activeSeg.text}
            </span>
          </div>
        )}
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
