"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useGraph, type GraphNode } from "@/hooks/useGraph";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
});

const GROUP_COLORS: Record<string, string> = {
  character: "#8b5cf6", // primary / violet
  scene: "#38bdf8", // muted blue
};

function nodeColor(node: GraphNode) {
  return GROUP_COLORS[node.group] || "#94a3b8";
}

export function NarrativeGraphView({ projectId }: { projectId: string }) {
  const { nodes, links } = useGraph(projectId);
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setWidth(entry.contentRect.width);
      }
    });
    observer.observe(el);
    setWidth(el.clientWidth);

    return () => observer.disconnect();
  }, []);

  return (
    <div className="rounded-xl border hairline bg-card h-[420px] flex flex-col">
      <div className="px-4 py-3 border-b hairline">
        <h2 className="text-sm font-medium">Narrative graph</h2>
        <p className="text-[11px] text-muted-foreground">
          Characters, relationships & scene appearances
        </p>
      </div>
      <div ref={containerRef} className="flex-1 min-h-0 relative">
        {nodes.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center px-6 text-center">
            <p className="text-xs text-muted-foreground">
              Narrative graph will populate as characters, scenes & agents run
            </p>
          </div>
        ) : width > 0 ? (
          <ForceGraph2D
            graphData={{ nodes, links }}
            width={width}
            height={372}
            nodeId="id"
            nodeLabel="label"
            nodeVal={4}
            nodeColor={(node: any) => nodeColor(node as GraphNode)}
            linkColor={() => "rgba(148, 163, 184, 0.4)"}
            backgroundColor="rgba(0,0,0,0)"
          />
        ) : null}
      </div>
    </div>
  );
}
