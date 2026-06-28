export interface EditFlag {
  id: string;
  clip_id: string;
  flag_type: EditFlagType;
  severity: "MINOR" | "MAJOR" | "REGENERATE_FULLY";
  description: string;
  direction: string | null;
  status: "OPEN" | "REGENERATING" | "RESOLVED" | "DISMISSED";
}

export type EditFlagType = "APPEARANCE" | "ACTION" | "LIGHTING" | "AUDIO" | "TIMING" | "OTHER";
