"use client";

import { cn } from "@/lib/utils";
import { useReducedMotion } from "@/hooks/useReducedMotion";

// inline SVG fractal noise tile — no request, GPU-cheap to composite.
// Shared with the dashboard's premiere empty state.
export const GRAIN = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`;

const RUNOUT = [
  "/poster2.jpg",
  "/poster3.jpg",
  "/poster4.jpg",
  "/poster6.jpg",
  "/poster8.jpg",
  "/poster10.jpg",
  "/poster13.jpg",
  "/poster15.jpg",
];

function MiniSprockets() {
  return (
    <div className="flex justify-center gap-2 py-[3px]">
      {Array.from({ length: 9 }).map((_, i) => (
        <span
          key={i}
          className="h-[4px] w-[3px] shrink-0 rounded-[1px] bg-zinc-700"
        />
      ))}
    </div>
  );
}

/**
 * Cinema atmosphere behind the final CTA: projector beam from above, live
 * film grain, and a reel running out along the bottom edge. Pure texture —
 * every layer sits behind the content and never intercepts the pointer.
 */
export function CtaBackdrop() {
  const reduced = useReducedMotion();

  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 z-0 overflow-hidden"
    >
      {/* 1 — projector beam: wide violet cone + tighter warm core, faint flutter */}
      <div
        className={cn(
          "absolute inset-0",
          !reduced && "animate-[projector-flutter_7s_linear_infinite]"
        )}
      >
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(120% 85% at 50% -20%, rgba(167,139,250,0.10), transparent 55%)",
          }}
        />
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(55% 45% at 50% -20%, rgba(255,255,255,0.05), transparent 60%)",
          }}
        />
      </div>

      {/* 2 — film grain, stepping through offsets so it shimmers */}
      <div
        className={cn(
          "absolute inset-0 opacity-[0.04] mix-blend-overlay",
          !reduced && "animate-[film-grain_0.8s_steps(1)_infinite]"
        )}
        style={{ backgroundImage: GRAIN }}
      />

      {/* 3 — reel run-out drifting along the bottom, fading to nothing above */}
      <div
        className="absolute inset-x-0 bottom-0"
        style={{
          maskImage:
            "linear-gradient(to right, transparent, black 12%, black 88%, transparent)",
          WebkitMaskImage:
            "linear-gradient(to right, transparent, black 12%, black 88%, transparent)",
        }}
      >
        <div
          style={{
            maskImage: "linear-gradient(to top, black 55%, transparent)",
            WebkitMaskImage: "linear-gradient(to top, black 55%, transparent)",
          }}
        >
          <div
            className={cn(
              "flex w-max opacity-[0.15] brightness-50",
              !reduced && "animate-[reel-left_120s_linear_infinite]"
            )}
          >
            {[0, 1].map((copy) =>
              RUNOUT.map((src) => (
                <div key={`${src}:${copy}`} className="shrink-0 pr-2">
                  <div className="w-[120px] rounded-[3px] border border-zinc-800 bg-zinc-950 px-1">
                    <MiniSprockets />
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={src}
                      alt=""
                      loading="lazy"
                      className="aspect-video w-full rounded-[2px] object-cover"
                    />
                    <MiniSprockets />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* vignette so the beam reads against darker corners */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(130% 110% at 50% 45%, transparent 55%, rgba(0,0,0,0.4) 100%)",
        }}
      />
    </div>
  );
}
