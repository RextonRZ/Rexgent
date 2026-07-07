import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";

export type UsageRange = "7d" | "30d" | "all";

export interface LlmModelRow {
  model: string;
  tokens: number;
  usd: number;
}

export interface UsageAnalytics {
  range: UsageRange;
  llm: {
    total_tokens: number;
    total_usd: number;
    all_premium_usd: number;
    saved_usd: number;
    cheap_share: number;
    by_model: LlmModelRow[];
  };
  categories: Record<string, { usd: number; quantity: number }>;
  dramas: {
    id: string;
    title: string;
    usd: number;
    runtime_seconds: number | null;
    clips: number;
    usd_per_min: number | null;
  }[];
  reliability: {
    clips_total: number;
    continuity_pass_rate: number | null;
    flagged: number;
    avg_face_score: number | null;
    by_tier: Record<string, { clips: number; retried: number; retry_rate: number }>;
  };
  trend: { date: string; usd: number; clips: number }[];
}

export function useUsageAnalytics(range: UsageRange) {
  return useQuery<UsageAnalytics>({
    queryKey: ["usage-analytics", range],
    queryFn: async () =>
      (await api.get(`/api/analytics/usage?range=${range}`)).data,
  });
}
