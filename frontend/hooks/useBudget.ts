import { useMutation } from "@tanstack/react-query";
import api from "@/lib/api";

export interface ScoredShot {
  shot_id: string;
  importance_score: number;
  quality_tier: "wan" | "happyhorse" | "happyhorse_fast";
  model: string;
  estimated_cost_usd: number;
  reasoning: string;
}

export interface BudgetResult {
  total_shots: number;
  total_estimated_seconds: number;
  budget_available: number;
  budget_reserved: number;
  scored_shots: ScoredShot[];
  wan_shots: number;
  happyhorse_shots: number;
  video_cost_usd: number;
  total_estimated_cost: number;
  budget_remaining: number;
  optimisation_summary: string;
}

export function useCalculateBudget() {
  return useMutation({
    mutationFn: async (projectId: string) => {
      const { data } = await api.post<BudgetResult>("/api/budget/calculate", {
        project_id: projectId,
        budget_usd: 40.0,
      });
      return data;
    },
  });
}
