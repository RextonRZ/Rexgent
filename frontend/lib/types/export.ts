export interface FinalExport {
  id: string;
  project_id: string;
  url: string | null;
  duration_seconds: number | null;
  caption_url: string | null;
  report_json: ProductionReport | null;
  created_at: string;
}

export interface ProductionReport {
  project_id: string;
  total_duration_seconds: number;
  total_clips: number;
  qwen_max_tokens_used: number;
  qwen_vl_calls: number;
  wan_clips: number;
  wan_seconds: number;
  happyhorse_clips: number;
  happyhorse_seconds: number;
  total_cost_usd: number;
  budget_used_pct: number;
  consistency_pass_rate: number;
  total_retries: number;
  wall_clock_minutes: number;
}
