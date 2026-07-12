import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export interface ApiKeyStatus {
  configured: boolean;
  tail: string | null;
  /** this deploy insists on a personal key for paid work */
  required: boolean;
  /** the server has its own fallback key (local dev) */
  server_fallback: boolean;
}

export function useApiKeyStatus() {
  return useQuery({
    queryKey: ["api-key"],
    queryFn: async () => {
      const { data } = await api.get<ApiKeyStatus>("/api/keys");
      return data;
    },
  });
}

export function useSaveApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (apiKey: string) => {
      const { data } = await api.put<ApiKeyStatus>("/api/keys", { api_key: apiKey });
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-key"] }),
  });
}

export function useDeleteApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.delete<ApiKeyStatus>("/api/keys");
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-key"] }),
  });
}
