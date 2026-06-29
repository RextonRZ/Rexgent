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
