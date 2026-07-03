import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import type { GeneratedClip } from "@/lib/types";

/** Every playable clip for the project, across ALL generation jobs — so older
 *  videos stay visible even after new (or empty duplicate) jobs and storyboard
 *  regenerations. */
export function useLatestJobClips(projectId: string) {
  return useQuery<{ clips: GeneratedClip[] }>({
    queryKey: ["clips", projectId],
    queryFn: async () => {
      const { data } = await api.get(`/api/generate/project/${projectId}/clips`);
      return data;
    },
    enabled: !!projectId,
    retry: false,
  });
}
