export interface Character {
  id: string;
  project_id: string;
  name: string;
  role: "PROTAGONIST" | "ANTAGONIST" | "SUPPORTING" | "MINOR" | null;
  gender: string | null;
  estimated_age: string | null;
  physical_description: string | null;
  personality_summary: string | null;
  mbti: string | null;
  mbti_confidence: number | null;
  speech_pattern: string | null;
  emotional_arc: EmotionalArc | null;
  reference_image_url: string | null;
  visual_description: string | null;
  video_prompt_fragment: string | null;
  face_keywords: string[] | null;
  /** "ref_rejected" = the uploaded photo was refused by the image service's
   *  content filter (recognizable public figures are blocked) */
  plate_status: string | null;
  created_at: string;
}

export interface EmotionalArc {
  start: string;
  midpoint: string;
  end: string;
}

export interface CharacterCreate {
  project_id: string;
  name: string;
  role?: string;
  gender?: string;
  estimated_age?: string;
  physical_description?: string;
}
