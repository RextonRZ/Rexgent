"use client";

import { useId, useState } from "react";
import type { ShotBlocking, BlockingSubject } from "@/lib/types";

/** Top-down mini shot-plan: the camera sits at the bottom throwing a soft
 * field-of-view cone up a stage; characters are colored directional markers
 * placed by screen side (x) and depth (y, nearer the camera = lower and
 * LARGER), each with a facing wedge and their name underneath. Posture
 * renders distinctly (lying = horizontal pill, seated = seat bar), curved
 * sky-tinted eyelines connect who looks at whom, and the camera is derived
 * from the shot type: tight shots creep closer and aim at their subject, an
 * OTS shoots from behind the foreground shoulder, a POV lines up with the
 * looker's eyes, wides swallow the stage.
 *
 * The encodings are self-explaining: hovering or tapping a marker spells its
 * geometry out in words under the stage, and the ? button opens a legend.
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
const DEPTH_WORDS: Record<string, string> = {
  FG: "near the camera",
  MG: "midground",
  BG: "far from the camera",
};

// per shot type: how wide the lens sees (a close-up is a sliver of stage, a
// wide swallows it) and how close the camera creeps to the actors
const CONE_SPREAD: Record<string, number> = {
  ECU: 13,
  CU: 16,
  MCU: 21,
  INSERT: 13,
  POV: 24,
  OTS: 24,
  MS: 28,
  FS: 33,
  WS: 36,
  LS: 38,
  EWS: 42,
};
const CAM_Y: Record<string, number> = {
  ECU: 51,
  CU: 52.5,
  MCU: 55,
  INSERT: 53,
};
const TIGHT = new Set(["ECU", "CU", "MCU", "INSERT"]);

/** Explicit posture wins; otherwise read it out of the subject's own action
 * prose ("lying unconscious on the bed" must not draw an upright pin). */
function posture(s: BlockingSubject): string | null {
  const p = (s.posture || "").toLowerCase().trim();
  if (p) return p;
  const act = String(s.action || "").toLowerCase();
  if (/collaps/.test(act)) return "collapsed";
  if (/\b(lying|lies|lie)\b|\bin bed\b/.test(act)) return "lying";
  if (/\b(sitting|seated|sits)\b/.test(act)) return "sitting";
  if (/\bkneel/.test(act)) return "kneeling";
  return null;
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
function movementArrow(movement: string | null | undefined, camX: number, camY: number) {
  const mv = (movement || "").toUpperCase();
  if (!mv || mv.includes("STATIC")) return null;
  const midY = camY + 2.7;
  if (mv.includes("LEFT"))
    return {
      line: [camX - 7, midY, camX - 14, midY],
      head: `M ${camX - 14} ${midY} l 2.6 -1.7 l 0 3.4 z`,
    };
  if (mv.includes("RIGHT"))
    return {
      line: [camX + 7, midY, camX + 14, midY],
      head: `M ${camX + 14} ${midY} l -2.6 -1.7 l 0 3.4 z`,
    };
  if (mv.includes("IN") || mv.includes("PUSH") || mv.includes("FORWARD"))
    return {
      line: [camX - 9, camY + 5, camX - 9, camY - 0.5],
      head: `M ${camX - 9} ${camY - 0.5} l -1.7 2.6 l 3.4 0 z`,
    };
  if (mv.includes("OUT") || mv.includes("PULL") || mv.includes("BACK"))
    return {
      line: [camX - 9, camY - 0.5, camX - 9, camY + 5],
      head: `M ${camX - 9} ${camY + 5} l -1.7 -2.6 l 3.4 0 z`,
    };
  return null;
}

export function BlockingDiagram({
  blocking,
  cameraMovement,
  shotType,
  faceByName,
}: {
  blocking: ShotBlocking;
  cameraMovement?: string | null;
  shotType?: string | null;
  /** Optional map of UPPER-CASED character name -> plate/face image URL. When a
   * token's character has a plate, it renders the photo inside the circle (the
   * identity colour becomes the ring); without one it falls back to the colour
   * fill. */
  faceByName?: Map<string, string | null | undefined>;
}) {
  const gradientId = useId();
  const [focusIdx, setFocusIdx] = useState<number | null>(null);
  const [pinnedIdx, setPinnedIdx] = useState<number | null>(null);
  const [showLegend, setShowLegend] = useState(false);
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
    return { s, x, y, r, depth, pose: posture(s) };
  });

  // ---- the camera, derived from the shot type ----
  const type = (shotType || "").toUpperCase().trim();
  const spread = CONE_SPREAD[type] ?? 28;
  const camY = CAM_Y[type] ?? 58;
  const fg = placed.find((t) => t.depth === "FG");
  const meanX =
    placed.reduce((sum, t) => sum + t.x, 0) / Math.max(placed.length, 1) || 50;
  const clampAim = (x: number) => Math.min(Math.max(x, 2 + spread), 98 - spread);

  let camX = 50;
  let aimX = clampAim(meanX);
  let camNote: string | null = null;
  if (type === "OTS" && fg) {
    // over the shoulder: behind the foreground character, aimed at the far one
    camX = fg.x + (fg.x <= 50 ? 7.5 : -7.5);
    const far = placed
      .filter((t) => t !== fg)
      .reduce<(typeof placed)[number] | null>(
        (a, b) => (a === null || b.y < a.y ? b : a),
        null
      );
    aimX = clampAim(far ? far.x : meanX);
    camNote = `over ${fg.s.character}'s shoulder`;
  } else if (type === "POV") {
    // point of view: the camera borrows a character's eyes — line up with the
    // subject facing into the scene (away from us), else the nearest one
    const looker =
      placed.find((t) => (t.s.facing || "").toLowerCase().includes("away")) ?? fg;
    if (looker) {
      camX = looker.x;
      const others = placed.filter((t) => t !== looker);
      aimX = clampAim(
        others.length
          ? others.reduce((sum, t) => sum + t.x, 0) / others.length
          : meanX
      );
      camNote = `through ${looker.s.character}'s eyes`;
    }
  } else if (TIGHT.has(type)) {
    // a close-up hunts its subject: aim at the single/most-foreground face
    // and creep the camera toward the action
    const primary = placed.length === 1 ? placed[0] : fg ?? placed[0];
    aimX = clampAim(primary.x);
    camX = 50 + (primary.x - 50) * 0.3;
    camNote = `close on ${primary.s.character}`;
  }
  const arrow = movementArrow(cameraMovement, camX, camY);

  // ---- eyelines: connect a looker to the character their eyeline names ----
  const eyelines: Array<{
    path: string;
    fromDot: { x: number; y: number } | null;
    toDot: { x: number; y: number };
    label: string;
    a: number;
    b: number;
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
      const x1 = a.x + ux * (a.r + 1.5);
      const y1 = a.y + uy * (a.r + 1.5);
      const x2 = b.x - ux * (b.r + 1.5);
      const y2 = b.y - uy * (b.r + 1.5);
      // bow the line upward so it never merges with the cone's straight edge
      let nx = -uy;
      let ny = ux;
      if (ny > 0) {
        nx = -nx;
        ny = -ny;
      }
      const qx = (x1 + x2) / 2 + nx * 4.5;
      const qy = (y1 + y2) / 2 + ny * 4.5;
      const mutual = eyelineMentions(
        String(b.s.eyeline || "").toUpperCase(),
        String(a.s.character || "")
      );
      eyelines.push({
        path: `M ${x1} ${y1} Q ${qx} ${qy} ${x2} ${y2}`,
        fromDot: mutual ? { x: x1, y: y1 } : null,
        toDot: { x: x2, y: y2 },
        label: mutual
          ? `${a.s.character} and ${b.s.character} look at each other`
          : `${a.s.character} looks at ${b.s.character}`,
        a: i,
        b: j,
      });
    });
  });

  const active = focusIdx ?? pinnedIdx;
  const focused = active != null ? placed[active] : null;
  const focusedLine =
    active != null ? eyelines.find((l) => l.a === active || l.b === active) : null;

  return (
    <div className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-1.5">
      <div className="mb-0.5 flex items-center justify-between px-0.5">
        <span className="text-[10px] uppercase tracking-widest text-zinc-300">
          blocking
        </span>
        <span className="flex items-center gap-1">
          {blocking.reverse_angle && (
            <span
              className="rounded bg-amber-500/15 px-1 text-[9px] font-medium text-amber-300"
              title="A deliberate cut across the line of action — everyone's screen sides re-establish from this shot"
            >
              reverse angle
            </span>
          )}
          <button
            onClick={() => setShowLegend((v) => !v)}
            title="What do the shapes mean?"
            className={`h-4 w-4 rounded-full text-[9px] font-semibold leading-none ${
              showLegend
                ? "bg-primary/30 text-primary"
                : "bg-white/[0.06] text-zinc-300 hover:bg-white/[0.12]"
            }`}
          >
            ?
          </button>
        </span>
      </div>

      <svg
        viewBox="0 0 100 68"
        className="block w-full"
        role="img"
        aria-label="Top-down stage plan for this shot"
        onMouseLeave={() => setFocusIdx(null)}
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

        {/* the camera's field of view: apex at the shot-specific camera,
            width from shot size, aimed at the shot's own subject(s) */}
        <polygon
          points={`${camX},${camY} ${aimX - spread},6 ${aimX + spread},6`}
          fill={`url(#${gradientId})`}
          stroke="rgba(139,92,246,0.14)"
          strokeWidth={0.3}
        />

        {/* who looks at whom — curved, sky-tinted, dotted at the looked-at end */}
        {eyelines.map((l, i) => {
          const involved = active == null || l.a === active || l.b === active;
          return (
            <g
              key={i}
              opacity={involved ? 0.95 : 0.25}
              style={{ transition: "opacity 120ms" }}
            >
              <title>{l.label}</title>
              <path
                d={l.path}
                fill="none"
                stroke="#7dd3fc"
                strokeWidth={involved && active != null ? 0.8 : 0.55}
                strokeDasharray="1.8 1.5"
              />
              <circle cx={l.toDot.x} cy={l.toDot.y} r={0.9} fill="#7dd3fc" />
              {l.fromDot && (
                <circle cx={l.fromDot.x} cy={l.fromDot.y} r={0.9} fill="#7dd3fc" />
              )}
            </g>
          );
        })}

        {placed.map(({ s, x, y, r, pose }, i) => {
          const color = slotFor(String(s.character || "?"));
          const lying = pose === "lying" || pose === "collapsed";
          const seated = pose === "sitting" || pose === "kneeling";
          const bodyR = seated ? r * 0.85 : r;
          const wedge = lying ? null : wedgePath(x, y, bodyR, s.facing);
          const halfBelow = lying ? r * 0.62 : seated ? r * 0.95 + 0.8 : r;
          const isActive = active === i;
          const dimmed = active != null && !isActive;
          const face = faceByName?.get(String(s.character || "").toUpperCase());
          const clipId = `${gradientId}-face-${i}`;
          return (
            <g
              key={`${s.character}-${i}`}
              opacity={dimmed ? 0.45 : 1}
              style={{ transition: "opacity 120ms", cursor: "pointer" }}
              onMouseEnter={() => setFocusIdx(i)}
              onClick={() => setPinnedIdx((p) => (p === i ? null : i))}
            >
              {lying ? (
                // a horizontal pill: someone lying in a bed or on the floor
                <>
                  {face && (
                    <>
                      <clipPath id={clipId}>
                        <rect
                          x={x - r * 1.5}
                          y={y - r * 0.62}
                          width={r * 3}
                          height={r * 1.24}
                          rx={r * 0.62}
                        />
                      </clipPath>
                      <image
                        href={face}
                        x={x - r * 1.5}
                        y={y - r * 0.62}
                        width={r * 3}
                        height={r * 1.24}
                        preserveAspectRatio="xMidYMid slice"
                        clipPath={`url(#${clipId})`}
                        opacity={isActive ? 1 : 0.9}
                      />
                    </>
                  )}
                  <rect
                    x={x - r * 1.5}
                    y={y - r * 0.62}
                    width={r * 3}
                    height={r * 1.24}
                    rx={r * 0.62}
                    fill={face ? "none" : color}
                    fillOpacity={isActive ? 0.32 : 0.18}
                    stroke={color}
                    strokeWidth={isActive ? 1.8 : 1.3}
                  />
                </>
              ) : (
                <>
                  {face && (
                    <>
                      <clipPath id={clipId}>
                        <circle cx={x} cy={y} r={bodyR} />
                      </clipPath>
                      <image
                        href={face}
                        x={x - bodyR}
                        y={y - bodyR}
                        width={bodyR * 2}
                        height={bodyR * 2}
                        preserveAspectRatio="xMidYMid slice"
                        clipPath={`url(#${clipId})`}
                        opacity={isActive ? 1 : 0.9}
                      />
                    </>
                  )}
                  <circle
                    cx={x}
                    cy={y}
                    r={bodyR}
                    fill={face ? "none" : color}
                    fillOpacity={isActive ? 0.32 : 0.18}
                    stroke={color}
                    strokeWidth={isActive ? 1.8 : 1.3}
                  />
                </>
              )}
              {seated && (
                // the seat bar under a sitting character
                <line
                  x1={x - r}
                  x2={x + r}
                  y1={y + r * 0.95}
                  y2={y + r * 0.95}
                  stroke={color}
                  strokeWidth={1.1}
                  strokeLinecap="round"
                />
              )}
              {wedge && <path d={wedge} fill={color} />}
              <text
                x={x}
                y={y + halfBelow + 5.5}
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
            {camNote
              ? `The camera, ${camNote}`
              : "The camera — nearer tokens are closer to it (foreground)"}
          </title>
          <rect
            x={camX - 4.5}
            y={camY}
            width={9}
            height={5.4}
            rx={1.4}
            fill="#27272a"
            stroke="#71717a"
            strokeWidth={0.7}
          />
          <circle
            cx={camX}
            cy={camY + 2.7}
            r={1.5}
            fill="none"
            stroke="#a1a1aa"
            strokeWidth={0.7}
          />
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

      {/* the hovered/tapped marker, spelled out in words */}
      {focused ? (
        <div className="flex items-start gap-1.5 px-0.5 pb-0.5 text-[10px] leading-snug text-zinc-200">
          <span
            className="mt-[3px] h-2 w-2 shrink-0 rounded-full"
            style={{ background: slotFor(String(focused.s.character || "?")) }}
          />
          <span>
            <span className="font-semibold">{focused.s.character}</span>
            {" · "}
            {focused.pose
              ? `${focused.pose}${focused.s.posture ? "" : " (from action)"}`
              : "standing"}
            {" · "}
            {DEPTH_WORDS[focused.depth] ?? "midground"}
            {focused.s.facing && ` · facing ${focused.s.facing}`}
            {focusedLine && (
              <>
                {" · "}
                <span className="text-sky-300">{focusedLine.label}</span>
              </>
            )}
            {focused.s.action && (
              <span className="italic text-zinc-400"> · {focused.s.action}</span>
            )}
          </span>
        </div>
      ) : (
        <div className="flex justify-between px-0.5 text-[10px] text-zinc-300">
          <span>screen left</span>
          <span>{camNote ? `camera ${camNote}` : "camera"}</span>
          <span>screen right</span>
        </div>
      )}

      {/* the legend: what every mark means */}
      {showLegend && (
        <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-1 border-t border-white/[0.07] px-0.5 pt-1.5 text-[10px] text-zinc-300">
          <span className="flex items-center gap-1.5">
            <svg viewBox="0 0 20 10" className="h-2.5 w-5 shrink-0">
              <circle cx={5} cy={5} r={4} fill="none" stroke="#a1a1aa" strokeWidth={1} />
              <circle cx={15} cy={5} r={2.2} fill="none" stroke="#a1a1aa" strokeWidth={1} />
            </svg>
            bigger means closer to the camera
          </span>
          <span className="flex items-center gap-1.5">
            <svg viewBox="0 0 20 10" className="h-2.5 w-5 shrink-0">
              <circle cx={7} cy={4} r={3.2} fill="none" stroke="#a1a1aa" strokeWidth={1} />
              <path d="M 10 4 L 14 4 L 10.5 1.8 Z" fill="#a1a1aa" />
            </svg>
            the wedge points where they face
          </span>
          <span className="flex items-center gap-1.5">
            <svg viewBox="0 0 20 10" className="h-2.5 w-5 shrink-0">
              <rect x={3} y={2.5} width={14} height={5} rx={2.5} fill="none" stroke="#a1a1aa" strokeWidth={1} />
            </svg>
            a pill is someone lying down
          </span>
          <span className="flex items-center gap-1.5">
            <svg viewBox="0 0 20 10" className="h-2.5 w-5 shrink-0">
              <circle cx={10} cy={4} r={3} fill="none" stroke="#a1a1aa" strokeWidth={1} />
              <line x1={6} y1={8.6} x2={14} y2={8.6} stroke="#a1a1aa" strokeWidth={1.2} strokeLinecap="round" />
            </svg>
            a bar underneath is someone seated
          </span>
          <span className="flex items-center gap-1.5">
            <svg viewBox="0 0 20 10" className="h-2.5 w-5 shrink-0">
              <path d="M 2 8 Q 10 1 17 6" fill="none" stroke="#7dd3fc" strokeWidth={0.9} strokeDasharray="2 1.5" />
              <circle cx={17} cy={6} r={1.3} fill="#7dd3fc" />
            </svg>
            blue curve shows who looks at whom
          </span>
          <span className="flex items-center gap-1.5">
            <svg viewBox="0 0 20 10" className="h-2.5 w-5 shrink-0">
              <polygon points="10,9 4,1 16,1" fill="rgba(139,92,246,0.25)" />
            </svg>
            the cone is what the lens sees
          </span>
        </div>
      )}
    </div>
  );
}
