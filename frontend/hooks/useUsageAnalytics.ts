import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";

export type UsageRange = "7d" | "30d" | "all";

export interface LlmModelRow {
  model: string;
  tokens: number;
  usd: number;
}

/** A real clip behind a reliability number — evidence, not decoration. */
export interface ClipSample {
  url: string;
  /** persisted still — survives clip URL expiry; preferred over the video */
  poster?: string | null;
  title: string;
  shot_number: number | null;
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
  categories: Record<
    string,
    {
      usd: number;
      quantity: number;
      /** media events tag their model; pre-tagging rows fold into "untracked" */
      by_model?: Record<string, { usd: number; quantity: number }>;
    }
  >;
  dramas: {
    id: string;
    title: string;
    poster_url: string | null;
    genre: string | null;
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
    flagged_samples?: ClipSample[];
    retried_samples?: ClipSample[];
  };
  /** recent drama posters for the routing hero's faint backdrop */
  hero_stills?: string[];
  trend: { date: string; usd: number; clips: number }[];
}

export function useUsageAnalytics(range: UsageRange) {
  return useQuery<UsageAnalytics>({
    queryKey: ["usage-analytics", range],
    queryFn: async () =>
      (await api.get(`/api/analytics/usage?range=${range}`)).data,
  });
}
