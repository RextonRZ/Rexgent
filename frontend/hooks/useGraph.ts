import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { getSocket } from "@/lib/websocket";

export interface GraphCharacter {
  id: string;
  name: string;
  role: string;
}

export interface GraphRelationship {
  id: string;
  from_char_id: string;
  to_char_id: string;
  rel_type: string;
  strength: number;
  description: string | null;
}

export interface GraphScene {
  number: number;
  heading: string;
  characters: string[];
}

export interface GraphResponse {
  characters: GraphCharacter[];
  relationships: GraphRelationship[];
  scenes: GraphScene[];
}

export interface GraphNode {
  id: string;
  label: string;
  group: "character" | "scene";
}

export interface GraphLink {
  source: string;
  target: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

const EMPTY_GRAPH: GraphData = { nodes: [], links: [] };

function shapeGraph(data?: GraphResponse): GraphData {
  if (!data) return EMPTY_GRAPH;

  const characters = data.characters ?? [];
  const relationships = data.relationships ?? [];
  const scenes = data.scenes ?? [];

  const nodes: GraphNode[] = [];
  const links: GraphLink[] = [];

  const charByName = new Map<string, GraphCharacter>();
  for (const c of characters) {
    nodes.push({ id: c.id, label: c.name, group: "character" });
    charByName.set(c.name, c);
  }

  for (const s of scenes) {
    nodes.push({
      id: `scene-${s.number}`,
      label: s.heading || `Scene ${s.number}`,
      group: "scene",
    });
  }

  for (const r of relationships) {
    links.push({ source: r.from_char_id, target: r.to_char_id });
  }

  for (const s of scenes) {
    for (const name of s.characters ?? []) {
      const character = charByName.get(name);
      if (!character) continue;
      links.push({ source: character.id, target: `scene-${s.number}` });
    }
  }

  return { nodes, links };
}

export function useGraph(projectId: string) {
  const queryClient = useQueryClient();

  const query = useQuery<GraphResponse>({
    queryKey: ["graph", projectId],
    queryFn: async () => (await api.get(`/api/graph/${projectId}`)).data,
    enabled: !!projectId,
  });

  useEffect(() => {
    if (!projectId) return;

    const socket = getSocket();
    socket.connect();
    socket.emit("join_project", { project_id: projectId });

    const handler = () => {
      queryClient.invalidateQueries({ queryKey: ["graph", projectId] });
    };
    socket.on("agent:report", handler);

    return () => {
      socket.off("agent:report", handler);
      socket.disconnect();
    };
  }, [projectId, queryClient]);

  return shapeGraph(query.data);
}
