export interface PlotFlag {
  id: string;
  script_id: string;
  scene_id: string | null;
  flag_type: PlotFlagType;
  severity: Severity;
  scene_number: number | null;
  description: string;
  evidence: string | null;
  suggestion: string | null;
  status: "OPEN" | "ACKNOWLEDGED" | "FIXED" | "DISMISSED";
}

export type PlotFlagType =
  | "MISSING_MOTIVATION"
  | "CONTINUITY_BREAK"
  | "UNRESOLVED_THREAD"
  | "PACING_ISSUE"
  | "CHARACTER_INCONSISTENCY";

export type Severity = "MINOR" | "MAJOR" | "CRITICAL";
