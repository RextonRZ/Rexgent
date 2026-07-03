import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import type { CharacterRelationship } from "@/lib/types";

export interface GraphScene {
  number: number;
  heading: string | null;
  characters: string[];
  image?: string | null;
  description?: string | null;
  emotional_beat?: string | null;
}

export interface GraphCharacterInfo {
  id: string;
  name: string;
  role: string;
  reference_image_url?: string | null;
}

export interface GraphData {
  characters: GraphCharacterInfo[];
  relationships: CharacterRelationship[];
  scenes: GraphScene[];
}

export function useGraph(projectId: string) {
  return useQuery<GraphData>({
    queryKey: ["graph", projectId],
    queryFn: async () => {
      const { data } = await api.get(`/api/graph/${projectId}`);
      return data;
    },
    enabled: !!projectId,
  });
}

export function useBuildRelationshipGraph() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (projectId: string) => {
      const { data } = await api.post("/api/graph/relationship", {
        project_id: projectId,
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["graph"] });
    },
  });
}
