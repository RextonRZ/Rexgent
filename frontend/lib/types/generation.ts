export interface GenerationJob {
  id: string;
  project_id: string;
  status: "PENDING" | "RUNNING" | "COMPLETE" | "FAILED" | "PAUSED" | "BUDGET_EXHAUSTED";
  total_shots: number | null;
  completed_shots: number;
  estimated_cost: number | null;
  actual_cost: number;
  created_at: string;
  completed_at: string | null;
}

/** One bible reference that conditioned a clip's generation. */
export interface ClipReference {
  url: string;
  role: "identity" | "costume" | "prev_frame" | "location" | "style";
  character?: string;
}

export interface GeneratedClip {
  id: string;
  job_id: string;
  shot_id: string;
  model_used: string | null;
  prompt: string | null;
  url: string | null;
  consistency_score: number | null;
  references_json?: ClipReference[] | null;
  seed?: number | null;
  cost_usd?: number | null;
  status: ClipStatus;
  retries: number;
  created_at: string;
}

export type ClipStatus = "PENDING" | "GENERATING" | "CHECKING" | "APPROVED" | "FAILED" | "NEEDS_REVIEW" | "TIMEOUT" | "SKIPPED";
