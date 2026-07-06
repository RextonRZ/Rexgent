import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import type { Shot } from "@/lib/types";

export interface SceneShots {
  scene_number: number;
  heading: string | null;
  shots: Shot[];
}

export function useStoryboard(projectId: string) {
  return useQuery<{ scenes: SceneShots[] }>({
    queryKey: ["storyboard", projectId],
    queryFn: async () => {
      const { data } = await api.get(`/api/storyboard/project/${projectId}`);
      return data;
    },
    enabled: !!projectId,
  });
}

export function useGenerateStoryboard() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (projectId: string) => {
      // Can include writing the screenplay first when the saved text has no
      // scenes yet — give it room beyond the default timeout.
      const { data } = await api.post(
        "/api/storyboard/generate",
        { project_id: projectId },
        { timeout: 420000 }
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["storyboard"] });
      // location plates are generated alongside the storyboard
      queryClient.invalidateQueries({ queryKey: ["bible"] });
    },
  });
}

export function useUpdateShot() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      shotId,
      updates,
    }: {
      shotId: string;
      updates: Partial<Shot>;
    }) => {
      const { data } = await api.patch(`/api/storyboard/${shotId}`, updates);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["storyboard"] });
    },
  });
}

export function useDeleteShot() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (shotId: string) => {
      const { data } = await api.delete(`/api/storyboard/${shotId}`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["storyboard"] });
    },
  });
}
