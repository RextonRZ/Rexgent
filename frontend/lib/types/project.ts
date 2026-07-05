export interface Project {
  id: string;
  title: string;
  genre: string | null;
  premise: string | null;
  status: string;
  poster_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  title: string;
  genre?: string;
  premise?: string;
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
