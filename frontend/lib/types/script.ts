export interface Script {
  id: string;
  project_id: string;
  raw_text: string | null;
  structured_json: StructuredScript | null;
  version: number;
  created_at: string;
}

export interface StructuredScript {
  title: string;
  genre: string;
  logline: string;
  acts: Act[];
  scenes: SceneData[];
  characters_mentioned: string[];
}

export interface Act {
  act_number: number;
  summary: string;
}

export interface SceneData {
  scene_number: number;
  act_number: number;
  heading: string;
  location: string;
  time_of_day: string;
  summary: string;
  characters_present: string[];
  dialogue_lines: DialogueLine[];
  stage_directions: string[];
  emotional_beat: string;
}

export interface DialogueLine {
  character: string;
  line: string;
  direction: string | null;
}

export interface Scene {
  id: string;
  script_id: string;
  number: number;
  title: string | null;
  heading: string | null;
  location: string | null;
  time_of_day: string | null;
  description: string | null;
  emotional_beat: string | null;
}
