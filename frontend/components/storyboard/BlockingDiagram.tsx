"use client";

import type { ShotBlocking, BlockingSubject } from "@/lib/types";

/** Top-down mini shot-plan: the camera sits at the bottom throwing a subtle
 * field-of-view fan up the stage; characters are colored tokens placed by
 * screen side (x) and depth (y, nearer the camera = lower), each with a
 * facing notch and their name directly underneath. The visible proof that
 * shots carry absolute geometry and consecutive shots hold the 180° line.
 *
 * Colors come from the validated dark-mode categorical set (8 slots, checked
 * against this app's #0b0912 surface: lightness band, chroma, ≥3:1 contrast;
 * CVD floor covered by the direct name labels). A character hashes to a slot
 * so their color is stable across every shot and scene — identity follows
 * the entity, never the shot's cast order. */
const SLOT_COLORS = [
  "#3987e5", // blue
  "#199e70", // aqua
  "#c98500", // yellow
  "#008300", // green
  "#9085e9", // violet
  "#e66767", // red
  "#d55181", // magenta
  "#d95926", // orange
];

function slotFor(name: string): string {
  let h = 0;
  for (const ch of name.toUpperCase()) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return SLOT_COLORS[h % SLOT_COLORS.length];
}

function shortName(name?: string): string {
  const first = (name || "?").trim().split(/\s+/)[0];
  return first.length > 7 ? first.slice(0, 6) + "…" : first;
}

const X: Record<string, number> = { left: 22, center: 50, right: 78 };
const Y: Record<string, number> = { BG: 14, MG: 28, FG: 42 };

function subjectTitle(s: BlockingSubject): string {
  return [
    s.character,
    s.frame_position,
    s.screen_side && `screen-${s.screen_side}`,
    s.facing && `facing ${s.facing}`,
    s.eyeline && `eyeline ${s.eyeline}`,
    s.action,
  ]
    .filter(Boolean)
    .join(" · ");
}

/** The facing notch: a small triangle on the token's rim. */
function notchPath(x: number, y: number, facing?: string): string | null {
  const f = (facing || "").toLowerCase();
  const r = 6;
  if (f.includes("screen-left"))
    return `M ${x - r} ${y} l 3.4 -2.4 l 0 4.8 z`;
  if (f.includes("screen-right"))
    return `M ${x + r} ${y} l -3.4 -2.4 l 0 4.8 z`;
  if (f.includes("away"))
    return `M ${x} ${y - r} l -2.4 3.4 l 4.8 0 z`;
  if (f.includes("toward"))
    return `M ${x} ${y + r} l -2.4 -3.4 l 4.8 0 z`;
  return null;
}

export function BlockingDiagram({ blocking }: { blocking: ShotBlocking }) {
  const subjects = (blocking.subjects ?? []).filter(
    (s): s is BlockingSubject => !!s && typeof s === "object"
  );
  // presence-only subjects (LLM drift) carry no geometry: show nothing
  // rather than a diagram that contradicts the prose
  if (!subjects.some((s) => s.screen_side || s.frame_position)) return null;

  // place tokens; several in one cell fan out horizontally
  const cellCount: Record<string, number> = {};
  const placed = subjects.map((s) => {
    const side = (s.screen_side || "center").toLowerCase();
    const depth = (s.frame_position || "MG").toUpperCase();
    const key = `${depth}-${side}`;
    const nth = cellCount[key] ?? 0;
    cellCount[key] = nth + 1;
    return { s, side, depth, nth };
  });

  return (
    <div className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-1.5">
      <div className="mb-0.5 flex items-center justify-between px-0.5">
        <span className="text-[9px] uppercase tracking-widest text-zinc-400">
          blocking
        </span>
        {blocking.reverse_angle && (
          <span
            className="rounded bg-amber-500/15 px-1 text-[9px] font-medium text-amber-300"
            title="A deliberate cut across the line of action — everyone's screen sides re-establish from this shot"
          >
            reverse angle
          </span>
        )}
      </div>

      <svg
        viewBox="0 0 100 68"
        className="block w-full"
        role="img"
        aria-label="Top-down stage plan for this shot"
      >
        {/* the camera's field of view, thrown up the stage */}
        <polygon
          points="50,58 12,6 88,6"
          fill="rgba(139,92,246,0.06)"
          stroke="rgba(139,92,246,0.18)"
          strokeWidth="0.4"
        />

        {placed.map(({ s, side, depth, nth }, i) => {
          const x = (X[side] ?? 50) + (nth === 0 ? 0 : nth % 2 === 1 ? 9 : -9);
          const y = Y[depth] ?? 28;
          const color = slotFor(String(s.character || "?"));
          const notch = notchPath(x, y, s.facing);
          return (
            <g key={`${s.character}-${i}`}>
              <title>{subjectTitle(s)}</title>
              <circle
                cx={x}
                cy={y}
                r={6}
                fill={color}
                fillOpacity={0.18}
                stroke={color}
                strokeWidth={1.3}
              />
              {notch && <path d={notch} fill={color} />}
              <text
                x={x}
                y={y + 12.5}
                textAnchor="middle"
                fontSize={4.8}
                fill="#d4d4d8"
                fontWeight={600}
              >
                {shortName(s.character)}
              </text>
            </g>
          );
        })}

        {/* the camera anchor */}
        <g>
          <title>The camera — nearer tokens are closer to it (foreground)</title>
          <rect x={45.5} y={58} width={9} height={5.4} rx={1.4}
                fill="#27272a" stroke="#71717a" strokeWidth={0.7} />
          <circle cx={50} cy={60.7} r={1.5} fill="none" stroke="#a1a1aa" strokeWidth={0.7} />
        </g>
      </svg>

      <div className="flex justify-between px-0.5 text-[9px] text-zinc-400">
        <span>screen left</span>
        <span>camera</span>
        <span>screen right</span>
      </div>
    </div>
  );
}
