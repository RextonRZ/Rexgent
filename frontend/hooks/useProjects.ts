import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import type { BudgetEstimate, Project, ProjectsOverview } from "@/lib/types";

export function useBudgetEstimate(params: {
  episode_count: number;
  target_length: number;
  characters?: number;
}) {
  return useQuery<BudgetEstimate>({
    queryKey: ["budget-estimate", params],
    queryFn: async () => {
      const { data } = await api.post("/api/projects/estimate_budget", params);
      return data;
    },
    staleTime: 60_000,
  });
}

export function useProjects() {
  return useQuery<{ projects: Project[] }>({
    queryKey: ["projects"],
    queryFn: async () => {
      const { data } = await api.get("/api/projects");
      return data;
    },
  });
}

export function useProject(projectId: string) {
  return useQuery<Project>({
    queryKey: ["project", projectId],
    queryFn: async () => {
      const { data } = await api.get(`/api/projects/${projectId}`);
      return data;
    },
    enabled: Boolean(projectId),
  });
}

export function useProjectsOverview() {
  return useQuery<ProjectsOverview>({
    queryKey: ["projects", "overview"],
    queryFn: async () => {
      const { data } = await api.get("/api/projects/overview");
      return data;
    },
  });
}

export function useUpdateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (params: {
      projectId: string;
      title?: string;
      poster_url?: string;
    }) => {
      const { projectId, ...body } = params;
      const { data } = await api.patch<Project>(
        `/api/projects/${projectId}`,
        body
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useDuplicateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (projectId: string) => {
      const { data } = await api.post<Project>(
        `/api/projects/${projectId}/duplicate`
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

// Poster capture happens server-side (ffmpeg): OSS serves clips without CORS
// headers, so drawing the video to a canvas in the browser taints it and
// toBlob() throws. The backend extracts the exact frame instead.
export function useSetPosterFromClip() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (params: {
      projectId: string;
      clipUrl: string;
      timestamp: number;
    }) => {
      const { data } = await api.post<{ poster_url: string }>(
        `/api/projects/${params.projectId}/poster/from_clip`,
        { clip_url: params.clipUrl, timestamp: params.timestamp }
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useSuggestTitle() {
  return useMutation({
    mutationFn: async (premise: string) => {
      const { data } = await api.post<{ title: string }>(
        "/api/projects/suggest_title",
        { premise }
      );
      return data.title;
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (projectId: string) => {
      const { data } = await api.delete(`/api/projects/${projectId}`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (params: {
      title: string;
      genre?: string;
      premise?: string;
      credit_budget?: number;
      token_budget?: number;
      video_ratio?: "9:16" | "16:9";
    }) => {
      const { data } = await api.post<Project>("/api/projects", params);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}
