"use client";

import { useId } from "react";
import type { ShotBlocking, BlockingSubject } from "@/lib/types";

/** Top-down mini shot-plan: the camera sits at the bottom throwing a soft
 * field-of-view cone up a stage; characters are colored directional markers
 * placed by screen side (x) and depth (y, nearer the camera = lower and
 * LARGER), each with a facing wedge and their name underneath. Dashed
 * eyelines connect characters who look at each other. The visible proof that
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
// closer to the camera = larger: depth you can read without a legend
const R: Record<string, number> = { BG: 4.5, MG: 6, FG: 7.5 };

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

/** The facing wedge: a triangle riding the token's rim, big enough to read
 * as a direction at a glance. */
function wedgePath(x: number, y: number, r: number, facing?: string): string | null {
  const f = (facing || "").toLowerCase();
  let dx = 0;
  let dy = 0;
  if (f.includes("screen-left")) dx = -1;
  else if (f.includes("screen-right")) dx = 1;
  else if (f.includes("away")) dy = -1;
  else if (f.includes("toward")) dy = 1;
  else return null;
  const tipX = x + dx * (r + 3.4);
  const tipY = y + dy * (r + 3.4);
  const baseX = x + dx * (r - 1.2);
  const baseY = y + dy * (r - 1.2);
  const px = dx === 0 ? 1 : 0; // perpendicular axis
  const py = dy === 0 ? 1 : 0;
  const half = Math.max(2.2, r * 0.42);
  return `M ${tipX} ${tipY} L ${baseX + px * half} ${baseY + py * half} L ${
    baseX - px * half
  } ${baseY - py * half} Z`;
}

const NAME_STOPWORDS = new Set(["THE", "AND", "HIS", "HER", "VON", "VAN", "DER"]);

/** Does this eyeline text mention this character? Full name first, then any
 * distinctive name token on a word boundary ("at Sun-jae" hits RYU SUN-JAE
 * without "at the letter" hitting THE STRANGER). */
function eyelineMentions(eyeline: string, character: string): boolean {
  const esc = (t: string) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const name = character.toUpperCase().trim();
  if (!name) return false;
  if (new RegExp(`\\b${esc(name)}\\b`).test(eyeline)) return true;
  return name
    .split(/[\s-]+/)
    .filter((t) => t.length >= 3 && !NAME_STOPWORDS.has(t))
    .some((t) => new RegExp(`\\b${esc(t)}\\b`).test(eyeline));
}

/** A small arrow beside the camera body for pan/dolly moves. */
function movementArrow(movement?: string | null) {
  const mv = (movement || "").toUpperCase();
  if (!mv || mv.includes("STATIC")) return null;
  if (mv.includes("LEFT"))
    return { line: [43, 60.7, 36, 60.7], head: "M 36 60.7 l 2.6 -1.7 l 0 3.4 z" };
  if (mv.includes("RIGHT"))
    return { line: [57, 60.7, 64, 60.7], head: "M 64 60.7 l -2.6 -1.7 l 0 3.4 z" };
  if (mv.includes("IN") || mv.includes("PUSH") || mv.includes("FORWARD"))
    return { line: [41, 63, 41, 57.5], head: "M 41 57.5 l -1.7 2.6 l 3.4 0 z" };
  if (mv.includes("OUT") || mv.includes("PULL") || mv.includes("BACK"))
    return { line: [41, 57.5, 41, 63], head: "M 41 63 l -1.7 -2.6 l 3.4 0 z" };
  return null;
}

export function BlockingDiagram({
  blocking,
  cameraMovement,
}: {
  blocking: ShotBlocking;
  cameraMovement?: string | null;
}) {
  const gradientId = useId();
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
    const x = (X[side] ?? 50) + (nth === 0 ? 0 : nth % 2 === 1 ? 9 : -9);
    const y = Y[depth] ?? 28;
    const r = R[depth] ?? 6;
    return { s, x, y, r };
  });

  // eyelines: connect a looker to the character their eyeline names
  const eyelines: Array<{
    x1: number;
    y1: number;
    x2: number;
    y2: number;
    label: string;
  }> = [];
  const linked = new Set<string>();
  placed.forEach((a, i) => {
    const eye = String(a.s.eyeline || "").toUpperCase();
    if (!eye) return;
    placed.forEach((b, j) => {
      if (i === j) return;
      if (!eyelineMentions(eye, String(b.s.character || ""))) return;
      const pair = `${Math.min(i, j)}-${Math.max(i, j)}`;
      if (linked.has(pair)) return;
      linked.add(pair);
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const d = Math.hypot(dx, dy) || 1;
      const ux = dx / d;
      const uy = dy / d;
      const mutual = eyelineMentions(
        String(b.s.eyeline || "").toUpperCase(),
        String(a.s.character || "")
      );
      eyelines.push({
        x1: a.x + ux * (a.r + 1.5),
        y1: a.y + uy * (a.r + 1.5),
        x2: b.x - ux * (b.r + 1.5),
        y2: b.y - uy * (b.r + 1.5),
        label: mutual
          ? `${a.s.character} and ${b.s.character} look at each other`
          : `${a.s.character} looks at ${b.s.character}`,
      });
    });
  });

  const arrow = movementArrow(cameraMovement);

  return (
    <div className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-1.5">
      <div className="mb-0.5 flex items-center justify-between px-0.5">
        <span className="text-[10px] uppercase tracking-widest text-zinc-300">
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
        <defs>
          {/* the cone glows from the lens and fades up the stage */}
          <linearGradient id={gradientId} x1="0" y1="1" x2="0" y2="0">
            <stop offset="0" stopColor="rgb(139,92,246)" stopOpacity="0.17" />
            <stop offset="1" stopColor="rgb(139,92,246)" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* the stage floor the actors stand on */}
        <rect
          x={8}
          y={6}
          width={84}
          height={44}
          rx={3}
          fill="rgba(255,255,255,0.025)"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={0.4}
        />

        {/* the camera's field of view, thrown up the stage */}
        <polygon
          points="50,58 12,6 88,6"
          fill={`url(#${gradientId})`}
          stroke="rgba(139,92,246,0.14)"
          strokeWidth={0.3}
        />

        {/* who looks at whom — drawn under the tokens */}
        {eyelines.map((l, i) => (
          <line
            key={i}
            x1={l.x1}
            y1={l.y1}
            x2={l.x2}
            y2={l.y2}
            stroke="#a1a1aa"
            strokeWidth={0.5}
            strokeDasharray="1.6 1.6"
            opacity={0.85}
          >
            <title>{l.label}</title>
          </line>
        ))}

        {placed.map(({ s, x, y, r }, i) => {
          const color = slotFor(String(s.character || "?"));
          const wedge = wedgePath(x, y, r, s.facing);
          return (
            <g key={`${s.character}-${i}`}>
              <title>{subjectTitle(s)}</title>
              <circle
                cx={x}
                cy={y}
                r={r}
                fill={color}
                fillOpacity={0.18}
                stroke={color}
                strokeWidth={1.3}
              />
              {wedge && <path d={wedge} fill={color} />}
              <text
                x={x}
                y={y + r + 5.5}
                textAnchor="middle"
                fontSize={5.2}
                fill="#e4e4e7"
                fontWeight={600}
              >
                {shortName(s.character)}
              </text>
            </g>
          );
        })}

        {/* the camera anchor */}
        <g>
          <title>
            {cameraMovement && !/static/i.test(cameraMovement)
              ? `The camera — ${String(cameraMovement).toLowerCase().replace(/_/g, " ")}`
              : "The camera — nearer tokens are closer to it (foreground)"}
          </title>
          <rect
            x={45.5}
            y={58}
            width={9}
            height={5.4}
            rx={1.4}
            fill="#27272a"
            stroke="#71717a"
            strokeWidth={0.7}
          />
          <circle cx={50} cy={60.7} r={1.5} fill="none" stroke="#a1a1aa" strokeWidth={0.7} />
          {arrow && (
            <g>
              <line
                x1={arrow.line[0]}
                y1={arrow.line[1]}
                x2={arrow.line[2]}
                y2={arrow.line[3]}
                stroke="#a1a1aa"
                strokeWidth={0.8}
              />
              <path d={arrow.head} fill="#a1a1aa" />
            </g>
          )}
        </g>
      </svg>

      <div className="flex justify-between px-0.5 text-[10px] text-zinc-300">
        <span>screen left</span>
        <span>camera</span>
        <span>screen right</span>
      </div>
    </div>
  );
}
