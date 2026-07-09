"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ElementType } from "react";
import { forceCollide } from "d3";
import { useGraph, type GraphLink, type GraphNode } from "@/hooks/useGraph";
import { Brain } from "lucide-react";

// force-graph hydrates our data: nodes gain sim coordinates, link endpoints
// may be raw ids or the hydrated node objects
type FGNode = GraphNode & { x?: number; y?: number };
type FGLink = Omit<GraphLink, "source" | "target"> & {
  source: string | FGNode;
  target: string | FGNode;
};
type ForceLike = {
  distance?: (n: number) => ForceLike;
  strength?: (n: number) => ForceLike;
};
interface ForceGraphHandle {
  d3Force(name: string): ForceLike | undefined;
  d3Force(name: string, force: unknown): void;
  d3ReheatSimulation?: () => void;
}

function Face({ node, size = 12 }: { node: FGNode | undefined; size?: number }) {
  const px = size * 4; // tailwind units → px
  return node?.img ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={node.img}
      alt={node.label}
      className="rounded-full object-cover border-2 border-primary/50 shrink-0"
      style={{ width: px, height: px }}
    />
  ) : (
    <div
      className="rounded-full bg-secondary flex items-center justify-center text-sm font-semibold text-muted-foreground shrink-0"
      style={{ width: px, height: px }}
    >
      {String(node?.label ?? "?").charAt(0)}
    </div>
  );
}

/** Right-side drawer explaining a clicked connection, with images —
 *  same pattern as the relationship edge panel on the Characters step. */
function ConnectionDrawer({
  link,
  source,
  target,
  onClose,
}: {
  link: FGLink;
  source: FGNode | undefined;
  target: FGNode | undefined;
  onClose: () => void;
}) {
  const isRel = link.kind === "relationship";
  return (
    <div className="fixed right-0 top-14 z-50 h-[calc(100vh-3.5rem)] w-80 bg-background border-l hairline shadow-xl p-4 space-y-4 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">
          {isRel ? "Relationship" : "Scene appearance"}
        </h3>
        <button
          onClick={onClose}
          aria-label="Close"
          className="h-6 w-6 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary text-xs"
        >
          ✕
        </button>
      </div>

      {isRel ? (
        <>
          {/* who ↔ who, with faces */}
          <div className="flex items-center justify-center gap-4">
            <div className="flex flex-col items-center gap-1.5">
              <Face node={source} size={16} />
              <span className="text-xs font-medium">{source?.label}</span>
            </div>
            <span className="text-lg text-muted-foreground">↔</span>
            <div className="flex flex-col items-center gap-1.5">
              <Face node={target} size={16} />
              <span className="text-xs font-medium">{target?.label}</span>
            </div>
          </div>
          {link.label && (
            <p className="text-center">
              <span className="rounded-full bg-primary/15 text-primary px-2.5 py-1 text-[11px] font-medium">
                {link.label}
              </span>
            </p>
          )}
        </>
      ) : (
        <>
          {/* character → scene, scene shown as its plate */}
          <div className="flex items-center gap-3">
            <Face node={source} size={12} />
            <p className="text-xs">
              <span className="font-medium">{source?.label}</span>{" "}
              <span className="text-muted-foreground">appears in</span>
              {link.label && (
                <span className="ml-1 text-primary/80">{link.label}</span>
              )}
              {(link.shots?.length ?? 0) > 0 && (
                <span className="ml-1 text-muted-foreground">
                  · shot{link.shots!.length === 1 ? "" : "s"}{" "}
                  {link.shots!.join(", ")}
                </span>
              )}
            </p>
          </div>
          {target?.img ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={target.img}
              alt={target.label}
              className="w-full rounded-lg border hairline aspect-video object-cover"
            />
          ) : (
            <div className="w-full rounded-lg border border-dashed hairline aspect-video flex items-center justify-center text-[11px] text-muted-foreground">
              no location plate yet
            </div>
          )}
          <p className="text-xs font-medium">{target?.label}</p>
        </>
      )}

      <div className="border-t hairline pt-3 space-y-2">
        <p className="text-xs text-muted-foreground leading-relaxed">
          {link.info || "No description available."}
        </p>
        {link.beat && (
          <span className="inline-block rounded bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
            Beat · {link.beat}
          </span>
        )}
        {(link.facts?.length ?? 0) > 0 && (
          <div className="rounded-lg border border-primary/20 bg-primary/[0.05] p-2.5">
            <p className="mb-1 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-widest text-primary">
              <Brain className="size-3" /> established here
            </p>
            <ul className="space-y-1">
              {link.facts!.map((f, i) => (
                <li key={i} className="text-[11px] leading-4 text-foreground/85">
                  {f}
                </li>
              ))}
            </ul>
            <p className="mt-1.5 text-[9px] text-muted-foreground">
              from the narrative memory graph — later scenes stage against these
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export function NarrativeGraphView({ projectId }: { projectId: string }) {
  const { nodes, links } = useGraph(projectId);
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<ForceGraphHandle | null>(null);
  const [width, setWidth] = useState(0);
  const [selLink, setSelLink] = useState<FGLink | null>(null);
  const [hoverLink, setHoverLink] = useState<FGLink | null>(null);
  // stable identity so hover/select re-renders don't re-heat the layout
  const graphData = useMemo(() => ({ nodes, links }), [nodes, links]);

  // link.source/target may be raw ids or hydrated node objects
  const endNode = (end: string | FGNode | undefined): FGNode | undefined =>
    typeof end === "object" ? end : nodes.find((n) => n.id === end);

  // Client-only import that supports refs (next/dynamic doesn't forward them),
  // so we can spread the force layout out for readability.
  const [FG, setFG] = useState<ElementType | null>(null);
  useEffect(() => {
    let alive = true;
    import("react-force-graph-2d").then((m) => {
      if (alive) setFG(() => m.default);
    });
    return () => {
      alive = false;
    };
  }, []);

  // Longer links + repulsion + collision = big picture-nodes don't overlap.
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    fg.d3Force("link")?.distance?.(140);
    fg.d3Force("charge")?.strength?.(-320);
    fg.d3Force("collide", forceCollide(48));
  }, [FG, nodes.length]);

  // cache node images (character faces + scene plates) for canvas drawing.
  // NO crossOrigin: OSS sends no CORS headers, so an anonymous request fails
  // outright — a plain load "taints" the canvas but draws fine (we never read
  // pixels back). Nudge the sim on load so late images actually get painted.
  const imgCache = useRef(new Map<string, HTMLImageElement>()).current;
  useEffect(() => {
    for (const n of nodes) {
      if (n.img && !imgCache.has(n.id)) {
        const im = new Image();
        im.onload = () => fgRef.current?.d3ReheatSimulation?.();
        im.src = n.img;
        imgCache.set(n.id, im);
      }
    }
  }, [nodes, imgCache]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) setWidth(entry.contentRect.width);
    });
    observer.observe(el);
    setWidth(el.clientWidth);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="rounded-xl border hairline bg-card flex flex-col">
      <div className="px-4 py-3 border-b hairline">
        <h2 className="text-sm font-medium">Story graph</h2>
        <p className="text-[11px] text-muted-foreground">
          Who appears in which scene — click a connection to see what happens
        </p>
      </div>

      <div ref={containerRef} className="relative h-[420px]">
        {nodes.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center px-6 text-center">
            <p className="text-xs text-muted-foreground">
              The story graph fills in as you extract characters, build
              relationships, and generate scenes.
            </p>
          </div>
        ) : width > 0 && FG ? (
          <FG
            ref={fgRef}
            graphData={graphData}
            width={width}
            height={420}
            nodeId="id"
            linkColor={(l: FGLink) =>
              l === selLink
                ? "rgba(139,92,246,0.95)" // selected: violet
                : l === hoverLink
                ? "rgba(236,72,153,0.9)" // hovered: pink
                : "rgba(148,163,184,0.35)"
            }
            linkWidth={(l: FGLink) => (l === selLink || l === hoverLink ? 3 : 1.5)}
            onLinkHover={(l: FGLink | null) => {
              setHoverLink(l);
              if (containerRef.current)
                containerRef.current.style.cursor = l ? "pointer" : "default";
            }}
            onLinkClick={(l: FGLink) => setSelLink(l)}
            onBackgroundClick={() => setSelLink(null)}
            backgroundColor="rgba(0,0,0,0)"
            nodeCanvasObject={(node: FGNode, ctx: CanvasRenderingContext2D, scale: number) => {
              const x = node.x ?? 0;
              const y = node.y ?? 0;
              const isChar = node.group === "character";
              const img = imgCache.get(node.id);
              const ready = img && img.complete && img.naturalWidth > 0;
              ctx.lineWidth = 1.5 / scale;

              if (isChar) {
                // character: round face chip
                const r = 22;
                ctx.beginPath();
                ctx.arc(x, y, r, 0, 2 * Math.PI);
                ctx.fillStyle = "#1c1633";
                ctx.fill();
                ctx.strokeStyle = "#8b5cf6";
                ctx.stroke();
                if (ready) {
                  ctx.save();
                  ctx.beginPath();
                  ctx.arc(x, y, r - 1, 0, 2 * Math.PI);
                  ctx.clip();
                  // cover-fit so portrait photos aren't stretched into the circle
                  const ar = img!.naturalWidth / img!.naturalHeight;
                  let dw = r * 2;
                  let dh = dw / ar;
                  if (dh < r * 2) {
                    dh = r * 2;
                    dw = dh * ar;
                  }
                  ctx.drawImage(img!, x - dw / 2, y - dh / 2, dw, dh);
                  ctx.restore();
                }
                ctx.font = `600 ${11 / scale}px sans-serif`;
                ctx.fillStyle = "#e7e9ee";
                ctx.textAlign = "center";
                ctx.fillText(node.label, x, y + r + 12 / scale);
              } else {
                // scene: location-plate thumbnail card
                const w = 76;
                const h = 48;
                ctx.beginPath();
                ctx.rect(x - w / 2, y - h / 2, w, h);
                ctx.fillStyle = "#101827";
                ctx.fill();
                ctx.strokeStyle = "#5aa9e6";
                ctx.stroke();
                if (ready) {
                  ctx.save();
                  ctx.beginPath();
                  ctx.rect(x - w / 2 + 1, y - h / 2 + 1, w - 2, h - 2);
                  ctx.clip();
                  // cover-fit the plate into the card
                  const ar = img!.naturalWidth / img!.naturalHeight;
                  let dw = w - 2;
                  let dh = dw / ar;
                  if (dh < h - 2) {
                    dh = h - 2;
                    dw = dh * ar;
                  }
                  ctx.drawImage(img!, x - dw / 2, y - dh / 2, dw, dh);
                  ctx.restore();
                }
                ctx.font = `${10 / scale}px sans-serif`;
                ctx.fillStyle = "#9aa3b2";
                ctx.textAlign = "center";
                const label =
                  node.label.length > 26
                    ? node.label.slice(0, 26) + "…"
                    : node.label;
                ctx.fillText(label, x, y + h / 2 + 11 / scale);
              }
            }}
          />
        ) : null}
      </div>

      {selLink && (
        <ConnectionDrawer
          link={selLink}
          source={endNode(selLink.source)}
          target={endNode(selLink.target)}
          onClose={() => setSelLink(null)}
        />
      )}

      <div className="flex items-center gap-4 px-4 py-2 border-t hairline text-[11px] text-muted-foreground">
        <span>
          <span
            className="inline-block h-2.5 w-2.5 rounded-full align-[-1px] mr-1"
            style={{ background: "#8b5cf6" }}
          />
          Character
        </span>
        <span>
          <span
            className="inline-block h-2.5 w-2.5 rounded-sm align-[-1px] mr-1"
            style={{ background: "#5aa9e6" }}
          />
          Scene
        </span>
        <span className="ml-auto">drag to explore</span>
      </div>
    </div>
  );
}
