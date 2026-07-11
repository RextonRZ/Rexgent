import { useMutation, useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import type { GenerationJob } from "@/lib/types";

export function useStartGeneration() {
  return useMutation({
    mutationFn: async (projectId: string) => {
      const { data } = await api.post("/api/generate/start", {
        project_id: projectId,
      });
      return data as GenerationJob;
    },
  });
}

/** The latest job, kept fresh while it runs — drives the dreaming tiles
 *  through page refreshes (the live socket store is session-only, so without
 *  this a mid-run refresh showed NOTHING for rendering shots). */
export function useLatestJobLive(projectId: string) {
  return useQuery<GenerationJob>({
    queryKey: ["generation-job-live", projectId],
    queryFn: async () => {
      const { data } = await api.get(
        `/api/generate/project/${projectId}/latest`
      );
      return data;
    },
    enabled: !!projectId,
    retry: false,
    refetchInterval: (q) =>
      q.state.data?.status === "RUNNING" || q.state.data?.status === "PENDING"
        ? 5000
        : false,
  });
}

export function useLatestJob(projectId: string) {
  return useQuery<GenerationJob>({
    queryKey: ["generation-job", projectId],
    queryFn: async () => {
      const { data } = await api.get(
        `/api/generate/project/${projectId}/latest`
      );
      return data;
    },
    enabled: false,
  });
}
