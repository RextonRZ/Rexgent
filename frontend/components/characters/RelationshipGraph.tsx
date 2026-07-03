"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { CharacterRelationship } from "@/lib/types";

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  name: string;
  role: string;
  reference_image_url?: string | null;
}

interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
  rel: CharacterRelationship;
}

interface RelationshipGraphProps {
  characters: {
    id: string;
    name: string;
    role: string;
    reference_image_url?: string | null;
  }[];
  relationships: CharacterRelationship[];
  onSelectEdge?: (rel: CharacterRelationship) => void;
}

const REL_COLORS: Record<string, string> = {
  ROMANTIC: "#ec4899",
  RIVAL: "#ef4444",
  FAMILY: "#3b82f6",
  MENTOR: "#f59e0b",
  ALLY: "#22c55e",
  ENEMY: "#dc2626",
  STRANGER: "#9ca3af",
  COLLEAGUE: "#8b5cf6",
};

const ROLE_RADIUS: Record<string, number> = {
  PROTAGONIST: 28,
  ANTAGONIST: 24,
  SUPPORTING: 20,
  MINOR: 16,
};

export function RelationshipGraph({
  characters,
  relationships,
  onSelectEdge,
}: RelationshipGraphProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    if (!svgRef.current || characters.length === 0) return;

    const width = 640;
    const height = 460;

    const nodes: GraphNode[] = characters.map((c) => ({ ...c }));
    const nodeById = new Map(nodes.map((n) => [n.id, n]));
    const links: GraphLink[] = relationships
      .filter((r) => nodeById.has(r.from_char_id) && nodeById.has(r.to_char_id))
      .map((r) => ({
        source: r.from_char_id,
        target: r.to_char_id,
        rel: r,
      }));

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("viewBox", `0 0 ${width} ${height}`);

    const tooltip = svg.append("g").style("pointer-events", "none");

    const simulation = d3
      .forceSimulation<GraphNode>(nodes)
      .force(
        "link",
        d3
          .forceLink<GraphNode, GraphLink>(links)
          .id((d) => d.id)
          .distance(140)
      )
      .force("charge", d3.forceManyBody().strength(-350))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collide", d3.forceCollide(34));

    const link = svg
      .append("g")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", (d) => REL_COLORS[d.rel.rel_type] || "#9ca3af")
      .attr("stroke-width", (d) => 1 + (d.rel.strength || 5) / 2.5)
      .attr("stroke-dasharray", (d) =>
        d.rel.rel_type === "ENEMY" ? "6 4" : null
      )
      .attr("opacity", 0.7)
      .style("cursor", onSelectEdge ? "pointer" : "default");

    link
      .on("mouseover", function (event, d) {
        d3.select(this)
          .attr("opacity", 1)
          .attr("stroke-width", 3 + (d.rel.strength || 5) / 2.5);
        // the tooltip group is created before the nodes, so raise it above
        // them or the text renders behind the face images
        tooltip.raise();
        if (d.rel.evidence_quote) {
          tooltip.selectAll("*").remove();
          const [mx, my] = d3.pointer(event, svgRef.current);
          const text = `"${d.rel.evidence_quote}"`;
          const t = tooltip
            .append("text")
            .attr("x", mx + 8)
            .attr("y", my - 8)
            .attr("font-size", 11)
            .attr("fill", "#e7e9ee")
            .text(text.length > 60 ? text.slice(0, 60) + "..." : text);
          const bbox = (t.node() as SVGTextElement).getBBox();
          tooltip
            .insert("rect", "text")
            .attr("x", bbox.x - 6)
            .attr("y", bbox.y - 4)
            .attr("width", bbox.width + 12)
            .attr("height", bbox.height + 8)
            .attr("fill", "#161b26")
            .attr("stroke", "#333c4f")
            .attr("rx", 5);
        }
      })
      .on("mouseout", function (_event, d) {
        d3.select(this)
          .attr("opacity", 0.7)
          .attr("stroke-width", 1 + (d.rel.strength || 5) / 2.5);
        tooltip.selectAll("*").remove();
      })
      .on("click", (_event, d) => {
        if (onSelectEdge) onSelectEdge(d.rel);
      });

    const node = svg
      .append("g")
      .selectAll<SVGGElement, GraphNode>("g")
      .data(nodes)
      .join("g")
      .call(
        d3
          .drag<SVGGElement, GraphNode>()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    const radius = (d: GraphNode) => ROLE_RADIUS[d.role] || 16;

    // face plate clipped to a circle when available, else a plain disc
    const defs = svg.append("defs");
    nodes.forEach((n) => {
      if (n.reference_image_url) {
        defs
          .append("clipPath")
          .attr("id", `rel-clip-${n.id}`)
          .append("circle")
          .attr("r", radius(n));
      }
    });

    node
      .append("circle")
      .attr("r", radius)
      .attr("fill", "#1e293b")
      .attr("stroke", "#8b5cf6")
      .attr("stroke-width", 2);

    node
      .filter((d) => !!d.reference_image_url)
      .append("image")
      .attr("href", (d) => d.reference_image_url!)
      .attr("x", (d) => -radius(d))
      .attr("y", (d) => -radius(d))
      .attr("width", (d) => radius(d) * 2)
      .attr("height", (d) => radius(d) * 2)
      .attr("preserveAspectRatio", "xMidYMid slice")
      .attr("clip-path", (d) => `url(#rel-clip-${d.id})`);

    node
      .append("text")
      .text((d) => d.name)
      .attr("text-anchor", "middle")
      .attr("dy", (d) => radius(d) + 16)
      .attr("font-size", 11)
      .attr("fill", "#c9cdd6");

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => (d.source as GraphNode).x ?? 0)
        .attr("y1", (d) => (d.source as GraphNode).y ?? 0)
        .attr("x2", (d) => (d.target as GraphNode).x ?? 0)
        .attr("y2", (d) => (d.target as GraphNode).y ?? 0);
      node.attr("transform", (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    return () => {
      simulation.stop();
    };
  }, [characters, relationships, onSelectEdge]);

  if (characters.length === 0) {
    return (
      <p className="text-center text-muted-foreground py-8">
        No characters to graph yet.
      </p>
    );
  }

  return (
    <div className="w-full">
      <svg ref={svgRef} className="w-full h-[460px]" />
      <div className="flex flex-wrap gap-3 text-xs mt-2">
        {Object.entries(REL_COLORS).map(([type, color]) => (
          <span key={type} className="flex items-center gap-1">
            <span
              className="inline-block w-3 h-0.5"
              style={{ backgroundColor: color }}
            />
            {type}
          </span>
        ))}
      </div>
    </div>
  );
}
