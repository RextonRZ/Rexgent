export interface ScoredShot {
  shot_id: string;
  importance_score: number;
  quality_tier: "wan" | "happyhorse" | "happyhorse_fast";
  model: string;
  estimated_cost_usd: number;
  reasoning: string;
}

export interface BudgetPlan {
  total_shots: number;
  total_estimated_seconds: number;
  budget_available: number;
  budget_reserved: number;
  scored_shots: ScoredShot[];
  wan_shots: number;
  happyhorse_shots: number;
  total_estimated_cost: number;
  budget_remaining: number;
  optimisation_summary: string;
}

export interface CostForecast {
  estimated_cost: number;
  budget_available: number;
  budget_remaining: number;
  over_budget: boolean;
}
