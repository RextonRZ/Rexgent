import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import type { Script } from "@/lib/types";

export function useScript(scriptId: string | null) {
  return useQuery<Script>({
    queryKey: ["script", scriptId],
    queryFn: async () => {
      const { data } = await api.get(`/api/script/${scriptId}`);
      return data;
    },
    enabled: !!scriptId,
  });
}

export function useGenerateScript() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (params: {
      project_id: string;
      genre: string;
      premise: string;
      tone?: string;
      episode_count?: number;
      target_length?: number;
      notes?: string;
      language?: string;
    }) => {
      const { data } = await api.post("/api/script/generate", params);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["script"] });
    },
  });
}

export function useUpdateScript() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      scriptId,
      rawText,
    }: {
      scriptId: string;
      rawText: string;
    }) => {
      const { data } = await api.patch(`/api/script/${scriptId}`, {
        raw_text: rawText,
      });
      return data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["script", variables.scriptId],
      });
    },
  });
}

export function useParseScript() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      file,
      projectId,
    }: {
      file: File;
      projectId: string;
    }) => {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("project_id", projectId);

      const { data } = await api.post("/api/script/parse", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["script"] });
    },
  });
}
