import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import api from "@/lib/api";
import { getSocket } from "@/lib/websocket";

export interface ProjectProgress {
  script: boolean;
  characters: boolean;
  storyboard: boolean;
  generate: boolean;
  export: boolean;
}

/** Which stages have real artifacts — refreshed whenever a stage finishes. */
export function useProjectProgress(projectId: string) {
  const queryClient = useQueryClient();
  const q = useQuery<ProjectProgress>({
    queryKey: ["progress", projectId],
    queryFn: async () =>
      (await api.get(`/api/projects/${projectId}/progress`)).data,
    enabled: !!projectId,
    staleTime: 10_000,
  });

  useEffect(() => {
    const socket = getSocket();
    socket.connect();
    socket.emit("join_project", { project_id: projectId });
    const invalidate = () =>
      queryClient.invalidateQueries({ queryKey: ["progress", projectId] });
    const events = ["stage:progress", "job:completed", "export.completed"];
    events.forEach((e) => socket.on(e, invalidate));
    return () => {
      events.forEach((e) => socket.off(e, invalidate));
      // no socket.disconnect() — the socket is shared app-wide
    };
  }, [projectId, queryClient]);

  return q.data;
}
