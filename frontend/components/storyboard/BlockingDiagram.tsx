"use client";

import { cn } from "@/lib/utils";
import type { ShotBlocking } from "@/lib/types";

/** The stage, seen as the frame: three columns (screen left / center / right)
 * by three depths (background on top, foreground nearest the viewer). Each
 * subject is a chip with a facing arrow — the visible proof that shots carry
 * absolute geometry and consecutive shots hold the 180-degree line. */

const SIDES = ["left", "center", "right"] as const;
const DEPTHS = ["BG", "MG", "FG"] as const;

function facingGlyph(facing?: string): string {
  const f = (facing || "").toLowerCase();
  if (f.includes("screen-left")) return "←";
  if (f.includes("screen-right")) return "→";
  if (f.includes("away")) return "↑";
  if (f.includes("toward")) return "●";
  return "";
}

function initials(name?: string): string {
  const n = (name || "?").trim();
  const parts = n.split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return n.slice(0, 2).toUpperCase();
}

export function BlockingDiagram({ blocking }: { blocking: ShotBlocking }) {
  const subjects = blocking.subjects ?? [];
  if (!subjects.length) return null;

  const cell = (depth: string, side: string) =>
    subjects.filter(
      (s) =>
        (s.frame_position || "MG").toUpperCase() === depth &&
        (s.screen_side || "center").toLowerCase() === side
    );

  return (
    <div className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-1.5">
      <div className="mb-1 flex items-center justify-between px-0.5">
        <span className="text-[9px] uppercase tracking-widest text-zinc-500">
          blocking
        </span>
        {blocking.reverse_angle && (
          <span className="rounded bg-amber-500/15 px-1 text-[9px] font-medium text-amber-300">
            reverse angle
          </span>
        )}
      </div>
      <div className="grid grid-cols-3 gap-0.5">
        {DEPTHS.map((depth) =>
          SIDES.map((side) => {
            const here = cell(depth, side);
            return (
              <div
                key={`${depth}-${side}`}
                className={cn(
                  "flex min-h-[22px] items-center justify-center gap-1 rounded",
                  // the frame reads nearer = brighter
                  depth === "FG"
                    ? "bg-white/[0.05]"
                    : depth === "MG"
                      ? "bg-white/[0.03]"
                      : "bg-white/[0.015]"
                )}
              >
                {here.map((s, i) => (
                  <span
                    key={`${s.character}-${i}`}
                    title={[
                      s.character,
                      s.frame_position,
                      s.screen_side && `screen-${s.screen_side}`,
                      s.facing && `facing ${s.facing}`,
                      s.eyeline && `eyeline ${s.eyeline}`,
                      s.action,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                    className="inline-flex items-center gap-0.5 rounded bg-violet-500/15 px-1 text-[9px] font-semibold text-violet-200"
                  >
                    {initials(s.character)}
                    <span className="font-normal text-violet-300/80">
                      {facingGlyph(s.facing)}
                    </span>
                  </span>
                ))}
              </div>
            );
          })
        )}
      </div>
      <div className="mt-0.5 flex justify-between px-0.5 text-[8px] text-zinc-600">
        <span>screen left</span>
        <span>camera ▼</span>
        <span>screen right</span>
      </div>
    </div>
  );
}
