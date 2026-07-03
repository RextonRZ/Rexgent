"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useGraph } from "@/hooks/useGraph";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
});

export function NarrativeGraphView({ projectId }: { projectId: string }) {
  const { nodes, links } = useGraph(projectId);
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);

  // load + cache character face images once, so the canvas can draw avatar chips
  const imgCache = useRef(new Map<string, HTMLImageElement>()).current;
  useEffect(() => {
    for (const n of nodes) {
      if (n.group === "character" && n.img && !imgCache.has(n.id)) {
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
          Characters, relationships &amp; scene appearances
        </p>
      </div>

      <div ref={containerRef} className="relative h-[340px]">
        {nodes.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center px-6 text-center">
            <p className="text-xs text-muted-foreground">
              The story graph fills in as you extract characters, build
              relationships, and generate scenes.
            </p>
          </div>
        ) : width > 0 ? (
          <ForceGraph2D
            graphData={{ nodes, links }}
            width={width}
            height={340}
            nodeId="id"
            linkColor={() => "rgba(148,163,184,0.35)"}
            backgroundColor="rgba(0,0,0,0)"
            nodeCanvasObject={(node: any, ctx, scale) => {
              const x = node.x ?? 0;
              const y = node.y ?? 0;
              const isChar = node.group === "character";
              const r = isChar ? 10 : 7;
              ctx.lineWidth = 1.5 / scale;
              ctx.fillStyle = isChar ? "#1c1633" : "#101827";
              ctx.strokeStyle = isChar ? "#8b5cf6" : "#5aa9e6";
              if (isChar) {
                ctx.beginPath();
                ctx.arc(x, y, r, 0, 2 * Math.PI);
                ctx.fill();
                ctx.stroke();
                const img = imgCache.get(node.id);
                if (img && img.complete && img.naturalWidth > 0) {
                  ctx.save();
                  ctx.beginPath();
                  ctx.arc(x, y, r - 1, 0, 2 * Math.PI);
                  ctx.clip();
                  ctx.drawImage(img, x - r, y - r, r * 2, r * 2);
                  ctx.restore();
                }
              } else {
                ctx.beginPath();
                ctx.rect(x - r, y - r * 0.7, r * 2, r * 1.4);
                ctx.fill();
                ctx.stroke();
              }
              ctx.font = `${11 / scale}px sans-serif`;
              ctx.fillStyle = "#c9cdd6";
              ctx.textAlign = "center";
              ctx.fillText(node.label, x, y + r + 11 / scale);
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
