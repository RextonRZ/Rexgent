"use client";

import { useEffect, useRef, useState } from "react";
import { useGraph } from "@/hooks/useGraph";

export function NarrativeGraphView({ projectId }: { projectId: string }) {
  const { nodes, links } = useGraph(projectId);
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<any>(null);
  const [width, setWidth] = useState(0);

  // Client-only import that supports refs (next/dynamic doesn't forward them),
  // so we can spread the force layout out for readability.
  const [FG, setFG] = useState<any>(null);
  useEffect(() => {
    let alive = true;
    import("react-force-graph-2d").then((m) => {
      if (alive) setFG(() => m.default);
    });
    return () => {
      alive = false;
    };
  }, []);

  // Longer links + stronger repulsion = nodes stop crowding each other.
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    fg.d3Force("link")?.distance(110);
    fg.d3Force("charge")?.strength(-260);
  }, [FG, nodes.length]);

  // cache node images (character faces + scene plates) for canvas drawing
  const imgCache = useRef(new Map<string, HTMLImageElement>()).current;
  useEffect(() => {
    for (const n of nodes) {
      if (n.img && !imgCache.has(n.id)) {
        const im = new Image();
        im.crossOrigin = "anonymous";
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
          Who appears in which scene — faces link to the scenes they&apos;re in
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
            graphData={{ nodes, links }}
            width={width}
            height={420}
            nodeId="id"
            linkColor={() => "rgba(148,163,184,0.35)"}
            backgroundColor="rgba(0,0,0,0)"
            nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, scale: number) => {
              const x = node.x ?? 0;
              const y = node.y ?? 0;
              const isChar = node.group === "character";
              const img = imgCache.get(node.id);
              const ready = img && img.complete && img.naturalWidth > 0;
              ctx.lineWidth = 1.5 / scale;

              if (isChar) {
                // character: round face chip
                const r = 16;
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
                  ctx.drawImage(img!, x - r, y - r, r * 2, r * 2);
                  ctx.restore();
                }
                ctx.font = `600 ${11 / scale}px sans-serif`;
                ctx.fillStyle = "#e7e9ee";
                ctx.textAlign = "center";
                ctx.fillText(node.label, x, y + r + 12 / scale);
              } else {
                // scene: location-plate thumbnail card
                const w = 46;
                const h = 30;
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
