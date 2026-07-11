export interface Shot {
  id: string;
  scene_id: string;
  number: number;
  shot_type: ShotType | null;
  camera_movement: CameraMovement | null;
  lighting: Lighting | null;
  colour_mood: ColourMood | null;
  action: string | null;
  dialogue: string | null;
  emotional_beat: string | null;
  estimated_duration_seconds: number;
  quality_tier: "wan" | "happyhorse" | "happyhorse_fast" | "deferred" | null;
  characters_in_frame: string[] | null;
  notes: string | null;
  director_note: string | null;
  blocking_json?: ShotBlocking | null;
}

/** Absolute per-shot geometry from the Director, 180-rule enforced. */
export interface ShotBlocking {
  subjects?: BlockingSubject[] | null;
  reverse_angle?: boolean;
}

export interface BlockingSubject {
  character?: string;
  frame_position?: "FG" | "MG" | "BG" | string;
  screen_side?: "left" | "center" | "right" | string;
  facing?: string;
  eyeline?: string;
  action?: string;
  posture?: "standing" | "sitting" | "lying" | "collapsed" | "kneeling" | string;
}

export type ShotType = "ECU" | "CU" | "MCU" | "MS" | "FS" | "LS" | "EWS" | "POV" | "OTS" | "INSERT";
export type CameraMovement = "STATIC" | "PAN_LEFT" | "PAN_RIGHT" | "TILT_UP" | "TILT_DOWN" | "DOLLY_IN" | "DOLLY_OUT" | "HANDHELD" | "DRONE";
export type Lighting = "NATURAL" | "GOLDEN_HOUR" | "BLUE_HOUR" | "NIGHT" | "OVERCAST" | "DRAMATIC_SIDE" | "NEON" | "PRACTICAL";
export type ColourMood = "WARM" | "COOL" | "DESATURATED" | "HIGH_CONTRAST" | "PASTEL" | "VIVID" | "MONOCHROME";
