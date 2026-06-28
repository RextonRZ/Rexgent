import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import type { Character } from "@/lib/types";

export function useCharacters(projectId: string) {
  return useQuery<{ characters: Character[] }>({
    queryKey: ["characters", projectId],
    queryFn: async () => {
      const { data } = await api.get(`/api/characters/project/${projectId}`);
      return data;
    },
    enabled: !!projectId,
  });
}

export function useExtractCharacters() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      projectId,
      inferMbti = false,
    }: {
      projectId: string;
      inferMbti?: boolean;
    }) => {
      const { data } = await api.post("/api/characters/extract", {
        project_id: projectId,
        infer_mbti: inferMbti,
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["characters"] });
    },
  });
}

export function useUpdateCharacter() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      characterId,
      updates,
    }: {
      characterId: string;
      updates: Partial<Character>;
    }) => {
      const { data } = await api.patch(
        `/api/characters/${characterId}`,
        updates
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["characters"] });
    },
  });
}
