export interface Project {
  id: string;
  title: string;
  genre: string | null;
  premise: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  title: string;
  genre?: string;
  premise?: string;
}
