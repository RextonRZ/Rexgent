import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import api from "@/lib/api";
import { getSocket } from "@/lib/websocket";
import type { Shot } from "@/lib/types";

export interface SceneShots {
  id: string;
  scene_number: number;
  episode?: number;
  heading: string | null;
  /** props every shot of this scene must render identically (set dresser) */
  set_items?: string[];
  /** prop state changes the action causes, e.g. a vase breaking mid scene */
  state_changes?: { from_shot: number; state: string }[];
  shots: Shot[];
}

export function useStoryboard(projectId: string) {
  const queryClient = useQueryClient();

  // boarding runs as a BACKGROUND job now — the page learns the board landed
  // (or died) from the stage events, not from an HTTP response
  useEffect(() => {
    if (!projectId) return;
    const socket = getSocket();
    socket.connect();
    socket.emit("join_project", { project_id: projectId });
    const onStage = (p: { stage?: string; status?: string }) => {
      if (p.stage === "storyboard" && (p.status === "completed" || p.status === "failed")) {
        queryClient.invalidateQueries({ queryKey: ["storyboard", projectId] });
        queryClient.invalidateQueries({ queryKey: ["bible", projectId] });
      }
    };
    socket.on("stage:progress", onStage);
    return () => {
      socket.off("stage:progress", onStage);
    };
  }, [projectId, queryClient]);

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

export function useDeleteScene() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (sceneId: string) => {
      const { data } = await api.delete(`/api/storyboard/scene/${sceneId}`);
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
