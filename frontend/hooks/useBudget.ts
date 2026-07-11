import { useMutation } from "@tanstack/react-query";
import api from "@/lib/api";

export interface ScoredShot {
  shot_id: string;
  importance_score: number;
  quality_tier: "wan" | "happyhorse" | "happyhorse_fast" | "deferred";
  model: string;
  is_hook?: boolean;
  estimated_cost_usd: number;
  reasoning: string;
}

export interface BudgetResult {
  total_shots: number;
  total_estimated_seconds: number;
  budget_usd?: number;
  budget_available: number;
  budget_reserved: number;
  scored_shots: ScoredShot[];
  wan_shots: number;
  happyhorse_shots: number;
  hook_shots?: number;
  downgraded_shots?: number;
  deferred_shots?: number;
  fits_budget?: boolean;
  recommended_budget_usd?: number | null;
  video_cost_usd: number;
  total_estimated_cost: number;
  budget_remaining: number;
  optimisation_summary: string;
  llm?: { input_tokens: number; output_tokens: number; cost_usd: number };
  llm_by_model?: Record<string, { tokens: number; usd: number }>;
  llm_cost_usd?: number;
  image_cost_usd?: number;
  tts_cost_usd?: number;
  grand_total_cost?: number;
  within_budget?: boolean;
}

export function useCalculateBudget() {
  return useMutation({
    mutationFn: async (projectId: string) => {
      // No budget_usd here: the backend reads this drama's own credit_budget,
      // so the plan is fitted to the cap the user actually set.
      const { data } = await api.post<BudgetResult>("/api/budget/calculate", {
        project_id: projectId,
      });
      return data;
    },
  });
}
