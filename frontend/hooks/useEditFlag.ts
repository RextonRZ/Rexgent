import { useMutation } from "@tanstack/react-query";
import api from "@/lib/api";

export function useFlagClip() {
  return useMutation({
    mutationFn: async (params: {
      clip_id: string;
      flag_type: string;
      severity: string;
      description: string;
      direction?: string;
    }) => {
      const { data } = await api.post("/api/edit/flag", params);
      return data as { flag_id: string; status: string };
    },
  });
}

export function useRegenClip() {
  return useMutation({
    mutationFn: async (params: { clip_id: string; flag_id: string }) => {
      const { data } = await api.post("/api/edit/regen", params);
      return data as {
        new_clip_id: string;
        new_url: string;
        original_url: string;
        changes_made: string[];
      };
    },
  });
}

export function useApproveClip() {
  return useMutation({
    mutationFn: async (clipId: string) => {
      const { data } = await api.post("/api/edit/approve", { clip_id: clipId });
      return data;
    },
  });
}
