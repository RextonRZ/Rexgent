"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { BTN_PRIMARY } from "@/components/ui/cta";
import { cn } from "@/lib/utils";
import api from "@/lib/api";
import { useSetPosterFromClip } from "@/hooks/useProjects";
import type { ProjectOverviewItem } from "@/lib/types";

interface PickerClip {
  id: string;
  url: string | null;
}

/**
 * Pick a poster frame from the drama's generated clips.
 *
 * Frame capture runs SERVER-SIDE (ffmpeg): our OSS bucket serves clips
 * without CORS headers, so a <canvas> drawImage + toBlob here would throw a
 * SecurityError (tainted canvas). The scrubber and thumbnails only preview;
 * "Use this frame" sends { clip_url, timestamp } to the backend.
 * The `#t=` media-fragment src on thumbnails shows a frame without playing.
 */
export function PosterPicker({
  project,
  onOpenChange,
}: {
  project: ProjectOverviewItem | null;
  onOpenChange: (v: boolean) => void;
}) {
  const setPoster = useSetPosterFromClip();
  const videoRef = useRef<HTMLVideoElement>(null);
  const [selectedUrl, setSelectedUrl] = useState<string | null>(null);
  const [duration, setDuration] = useState(0);
  const [time, setTime] = useState(0);

  const { data } = useQuery({
    queryKey: ["poster-clips", project?.id],
    enabled: Boolean(project),
    queryFn: async () => {
      const res = await api.get(`/api/generate/project/${project!.id}/clips`);
      return res.data as { clips: PickerClip[] };
    },
  });
  const clips = (data?.clips ?? []).filter((c) => c.url) as {
    id: string;
    url: string;
  }[];

  const url = selectedUrl ?? clips[0]?.url ?? null;

  // reset per drama
  useEffect(() => {
    setSelectedUrl(null);
    setDuration(0);
    setTime(0);
  }, [project?.id]);

  const seek = (t: number) => {
    const v = videoRef.current;
    if (!v || !duration) return;
    const clamped = Math.min(Math.max(0, t), Math.max(0, duration - 0.05));
    v.currentTime = clamped;
    setTime(clamped);
  };

  const suggested = duration
    ? Array.from({ length: 6 }, (_, i) => ((i + 1) * duration) / 7)
    : [];

  const useFrame = async () => {
    if (!project || !url) return;
    await setPoster.mutateAsync({
      projectId: project.id,
      clipUrl: url,
      timestamp: time,
    });
    onOpenChange(false);
  };

  return (
    <Dialog open={Boolean(project)} onOpenChange={onOpenChange}>
      <DialogContent className="glass sm:max-w-3xl" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>Change poster — {project?.title}</DialogTitle>
        </DialogHeader>

        {clips.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No clips yet — posters are cut from your generated footage.
          </p>
        ) : (
          <div className="flex gap-4 pt-2">
            {/* clip list */}
            <div className="flex max-h-[420px] w-40 shrink-0 flex-col gap-2 overflow-y-auto pr-1">
              {clips.map((c, i) => (
                <button
                  key={c.id}
                  onClick={() => {
                    setSelectedUrl(c.url);
                    setDuration(0);
                    setTime(0);
                  }}
                  className={cn(
                    "flex items-center gap-2 rounded-lg border p-1.5 text-left outline-none transition-colors",
                    url === c.url
                      ? "border-violet-500 bg-violet-500/10"
                      : "border-white/10 hover:border-white/25"
                  )}
                >
                  <video
                    src={`${c.url}#t=0.5`}
                    muted
                    playsInline
                    preload="metadata"
                    className="h-10 w-16 shrink-0 rounded object-cover"
                  />
                  <span className="text-[11px] text-zinc-300">
                    Take {i + 1}
                  </span>
                </button>
              ))}
            </div>

            {/* preview + scrubber */}
            <div className="min-w-0 flex-1 space-y-3">
              <video
                ref={videoRef}
                key={url ?? "none"}
                src={url ?? undefined}
                muted
                playsInline
                preload="metadata"
                onLoadedMetadata={(e) => {
                  setDuration(e.currentTarget.duration || 0);
                  setTime(e.currentTarget.currentTime || 0);
                }}
                className="aspect-video w-full rounded-lg border border-zinc-800 bg-black object-contain"
              />

              {/* auto-suggested frames */}
              {suggested.length > 0 && (
                <div className="grid grid-cols-6 gap-1.5">
                  {suggested.map((ts) => (
                    <button
                      key={ts}
                      onClick={() => seek(ts)}
                      title={`${ts.toFixed(1)}s`}
                      className="overflow-hidden rounded border border-white/10 outline-none transition-colors hover:border-violet-500/60 focus-visible:ring-2 focus-visible:ring-violet-400/60"
                    >
                      <video
                        src={`${url}#t=${ts.toFixed(2)}`}
                        muted
                        playsInline
                        preload="metadata"
                        className="aspect-video w-full object-cover"
                      />
                    </button>
                  ))}
                </div>
              )}

              <input
                type="range"
                min={0}
                max={duration || 0}
                step={0.05}
                value={time}
                onChange={(e) => seek(parseFloat(e.target.value))}
                aria-label="Scrub to frame"
                className="w-full accent-violet-500"
              />

              <div className="flex items-center gap-2">
                {[-1, -0.1, 0.1, 1].map((d) => (
                  <button
                    key={d}
                    onClick={() => seek(time + d)}
                    className="rounded-md border border-white/10 px-2 py-1 font-mono text-[11px] text-zinc-300 transition-colors hover:border-white/25"
                  >
                    {d > 0 ? `+${d}s` : `${d}s`}
                  </button>
                ))}
                <span className="ml-auto font-mono text-[11px] text-muted-foreground">
                  {time.toFixed(2)}s / {duration.toFixed(2)}s
                </span>
              </div>

              <Button
                onClick={useFrame}
                disabled={!url || setPoster.isPending}
                className={cn("h-10 w-full", BTN_PRIMARY)}
              >
                {setPoster.isPending ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    Capturing frame...
                  </>
                ) : (
                  <>
                    <Check className="size-4" />
                    Use this frame
                  </>
                )}
              </Button>
              {setPoster.isError && (
                <p className="text-sm text-destructive">
                  Could not capture that frame. Try another timestamp.
                </p>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
