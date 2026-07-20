"use client";

import { forwardRef, useEffect, useRef, useState } from "react";
import { Film } from "lucide-react";
import { cn } from "@/lib/utils";

/** A <video> that never LOOKS hung: a shimmer + spinner covers it until the
 * first frame is decodable, and a quiet film tile replaces a dead source.
 * `className` sizes the OUTER shell (aspect, width, rounding); the video
 * fills it with `fit` (cover|contain).
 *
 * `lazy` defers mounting the <video> until the tile scrolls near the viewport,
 * so a long grid of clips (the export shot library) stops firing dozens of OSS
 * metadata fetches on open. */
export const LoadingVideo = forwardRef<
  HTMLVideoElement,
  React.ComponentProps<"video"> & {
    fit?: "cover" | "contain";
    /** object-position, e.g. "50% 25%" to keep faces of portrait clips in frame */
    fitPosition?: string;
    lazy?: boolean;
  }
>(function LoadingVideo({ className, fit = "cover", fitPosition, lazy = false, children, ...rest }, ref) {
  const [ready, setReady] = useState(false);
  const [dead, setDead] = useState(false);
  const [inView, setInView] = useState(!lazy);
  const shellRef = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!lazy || inView) return;
    const el = shellRef.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setInView(true);
          io.disconnect();
        }
      },
      { rootMargin: "300px" }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [lazy, inView]);
  return (
    <span ref={shellRef} className={cn("relative block overflow-hidden", className)}>
      {!dead && inView && (
        <video
          ref={ref}
          {...rest}
          className={cn(
            "absolute inset-0 h-full w-full",
            fit === "cover" ? "object-cover" : "object-contain"
          )}
          style={fitPosition ? { objectPosition: fitPosition } : undefined}
          onLoadedData={(e) => {
            setReady(true);
            rest.onLoadedData?.(e);
          }}
          onCanPlay={(e) => {
            setReady(true);
            rest.onCanPlay?.(e);
          }}
          onError={(e) => {
            setDead(true);
            rest.onError?.(e);
          }}
        >
          {children}
        </video>
      )}
      {(!ready || dead) && (
        <span
          className={cn(
            "absolute inset-0 flex items-center justify-center bg-zinc-900",
            !dead && "motion-safe:animate-pulse"
          )}
        >
          {dead ? (
            <Film className="size-4 text-zinc-700" />
          ) : (
            <span className="h-4 w-4 rounded-full border-2 border-zinc-700 border-t-violet-400 motion-safe:animate-spin" />
          )}
        </span>
      )}
    </span>
  );
});
