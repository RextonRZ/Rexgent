export type VideoRatio = "9:16" | "16:9";

export interface Project {
  id: string;
  title: string;
  genre: string | null;
  premise: string | null;
  status: string;
  poster_url: string | null;
  credit_budget: number | null;
  token_budget: number | null;
  video_ratio?: VideoRatio | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  title: string;
  genre?: string;
  premise?: string;
  credit_budget?: number;
  token_budget?: number;
  video_ratio?: VideoRatio;
}

export interface BudgetEstimate {
  scope: { episodes: number; scenes: number; shots: number; video_seconds: number };
  credit_usd: number;
  credit_breakdown: { video: number; image: number; tts: number };
  llm_tokens: number;
}

export interface ProjectOverviewItem extends Project {
  clip_count: number;
  preview_clip_url: string | null;
  spent_usd: number;
  is_generating: boolean;
}

export interface RecentClip {
  url: string;
  project_id: string;
  project_title: string;
}

export interface ProjectsOverview {
  projects: ProjectOverviewItem[];
  recent_clips: RecentClip[];
  totals: {
    dramas: number;
    clips: number;
    film_seconds: number;
    spent_usd: number;
  };
}
