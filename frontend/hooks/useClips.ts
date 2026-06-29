import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import type { GeneratedClip } from "@/lib/types";

export function useLatestJobClips(projectId: string) {
  return useQuery<{ clips: GeneratedClip[] }>({
    queryKey: ["clips", projectId],
    queryFn: async () => {
      const { data: job } = await api.get(
        `/api/generate/project/${projectId}/latest`
      );
      const { data } = await api.get(`/api/generate/${job.id}/clips`);
      return data;
    },
    enabled: !!projectId,
    retry: false,
  });
}
