"use client";

import { cn } from "@/lib/utils";
import { useReducedMotion } from "@/hooks/useReducedMotion";
import { GRAIN } from "@/components/landing/CtaBackdrop";

/**
 * Page-wide cinematic atmosphere for the app (dashboard + pipeline pages):
 * two slow drifting violet auroras, a faint projector wash from the top, live
 * film grain and a corner vignette — the same language as the landing hero,
 * but quiet enough to sit behind working UI. Fixed, behind everything, never
 * intercepts the pointer.
 */
export function AmbientBackdrop() {
  const reduced = useReducedMotion();
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-[#07060d]"
    >
      {/* projector wash from above */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(120% 70% at 50% -10%, rgba(167,139,250,0.10), transparent 55%)",
        }}
      />
      {/* two drifting auroras */}
      <div
        className={cn(
          "absolute -left-[10%] top-[8%] h-[42vh] w-[42vw] rounded-full bg-violet-600/[0.14] blur-[100px]",
          !reduced && "animate-[aurora-drift_22s_ease-in-out_infinite]"
        )}
      />
      <div
        className={cn(
          "absolute right-[-8%] top-[38%] h-[46vh] w-[40vw] rounded-full bg-fuchsia-600/[0.10] blur-[120px]",
          !reduced && "animate-[aurora-drift-slow_28s_ease-in-out_infinite]"
        )}
      />
      {/* film grain */}
      <div
        className={cn(
          "absolute inset-0 opacity-[0.035] mix-blend-overlay",
          !reduced && "animate-[film-grain_0.8s_steps(1)_infinite]"
        )}
        style={{ backgroundImage: GRAIN }}
      />
      {/* vignette */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(130% 120% at 50% 40%, transparent 58%, rgba(0,0,0,0.55) 100%)",
        }}
      />
    </div>
  );
}
