import { useMutation } from "@tanstack/react-query";
import api from "@/lib/api";

export interface AutoRunResult {
  status: string;
  script_id: string | null;
  judgement: {
    overall?: number;
    recommendation?: string;
  } | null;
  characters: number;
  shots: number;
  budget: {
    total_estimated_cost?: number;
    grand_total_cost?: number;
    wan_shots?: number;
    happyhorse_shots?: number;
  } | null;
  job_id: string | null;
  dispatched: boolean;
  revisions: number;
}

export function useAutoRun() {
  return useMutation({
    mutationFn: async (params: {
      project_id: string;
      premise: string;
      genre: string;
      tone?: string;
      model?: string;
      language: string;
      target_length?: number;
      episode_count?: number;
      dispatch_video?: boolean;
    }) => {
      const { data } = await api.post<AutoRunResult>("/api/agent/auto", params);
      return data;
    },
  });
}
