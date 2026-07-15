import {
  Brain,
  Clapperboard,
  GitBranch,
  Scale,
  Search,
  Share2,
  Wand2,
  Database,
  Film,
  Image,
  Lamp,
  ListTree,
  PenLine,
  RefreshCw,
  ScanFace,
  Scissors,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Type,
  Upload,
  UserRound,
  Users,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import type { StageKey } from "@/hooks/useLiveRun";

/** ── the crew workflow topology ──────────────────────────────────────────
 * The FIXED set of tools each stage orchestrates. Required (auto) nodes come
 * FIRST, in run order; conditional/on-demand nodes sit at the BACK (they fire
 * only when their trigger holds, so an idle one is healthy). Idle nodes render
 * faint from this list before any event arrives; live `tools` state from
 * useLiveRunStore overlays running/done/failed per node. A tool the backend
 * emits that isn't listed here still renders (appended dynamically), so the
 * graph can never hide real machinery.
 */
export interface ToolSpec {
  key: string;
  icon: LucideIcon;
  /** what kind of node this is — shapes the tooltip copy */
  kind: "llm" | "db" | "validator" | "media" | "service";
  /** how the node runs. Omitted = "auto": fires by itself, in this order,
   * every time the stage runs. "conditional": fires by itself but only when
   * its condition holds — idle is healthy. "on-demand": fires only when the
   * user takes an action — never blocks the stage. */
  run?: "conditional" | "on-demand";
  /** for conditional/on-demand nodes: one line saying what makes it fire */
  trigger?: string;
}

export const STAGE_AGENT: Record<StageKey, string> = {
  script: "Screenwriter",
  characters: "Casting Director",
  storyboard: "Director",
  generate: "Showrunner",
  export: "Editor",
};

export const STAGE_AGENT_ICONS: Record<StageKey, LucideIcon> = {
  script: PenLine,
  characters: Users,
  storyboard: Clapperboard,
  generate: Film,
  export: Scissors,
};

export const STAGE_TOOLS: Record<StageKey, ToolSpec[]> = {
  script: [
    { key: "develop_story", icon: Wand2, kind: "llm" },
    { key: "llm_write", icon: Sparkles, kind: "llm" },
    { key: "structure_scenes", icon: ListTree, kind: "llm" },
    { key: "write_script_db", icon: Database, kind: "db" },
    {
      key: "narrative_judge", icon: Scale, kind: "validator",
      run: "conditional",
      trigger: "Full Auto judges every draft automatically; on the Script page it runs when you press Score Quality",
    },
    {
      key: "plot_gap_check", icon: Search, kind: "validator",
      run: "on-demand",
      trigger: "press Run AI Analysis on the Script page to scan for plot holes",
    },
    {
      key: "ending_engine", icon: GitBranch, kind: "llm",
      run: "on-demand",
      trigger: "runs with Run AI Analysis to grade the ending and pitch alternates",
    },
  ],
  characters: [
    { key: "extract_cast", icon: Users, kind: "llm" },
    { key: "write_cast_db", icon: Database, kind: "db" },
    { key: "generate_plates", icon: Image, kind: "media" },
    {
      key: "map_relationships", icon: Share2, kind: "llm",
      run: "conditional",
      trigger: "builds itself right after extraction, and heals on page load if the bonds are missing",
    },
    {
      key: "profile_cast", icon: UserRound, kind: "llm",
      run: "conditional",
      trigger: "runs by itself inside Generate Plates for any character still missing a look; Generate Appearance (no photo) on a character card re-runs it for one character",
    },
    {
      key: "face_lock", icon: ScanFace, kind: "validator",
      run: "conditional",
      trigger: "locks automatically when plates capture a clear face; uploading a reference photo on a character card locks a real look instead",
    },
  ],
  storyboard: [
    { key: "memory_recall", icon: Brain, kind: "db" },
    { key: "shot_breakdown", icon: Clapperboard, kind: "llm" },
    { key: "set_design", icon: Lamp, kind: "llm" },
    { key: "write_shots_db", icon: Database, kind: "db" },
  ],
  // budget_allocate is deliberately NOT predeclared: it fires on the
  // Storyboard page (pre-production), so a permanent idle node here read as
  // broken — when it does run, the graph appends it dynamically with its
  // artifact, so the Producer still shows up the moment money gets fitted.
  generate: [
    { key: "prompt_craft", icon: Wand2, kind: "llm" },
    { key: "dispatch_video", icon: Film, kind: "media" },
    { key: "verify_face", icon: ShieldCheck, kind: "validator" },
    { key: "write_clip_db", icon: Database, kind: "db" },
    {
      key: "self_correct", icon: RefreshCw, kind: "service",
      run: "conditional",
      trigger: "only when a render fails and the crew retries it — idle means nothing broke",
    },
    {
      key: "fix_take", icon: Wrench, kind: "llm",
      run: "on-demand",
      trigger: "press Fix take on a flagged clip in the Edit room",
    },
  ],
  export: [
    { key: "stitch_clips", icon: Film, kind: "media" },
    { key: "render_mp4", icon: Upload, kind: "media" },
    { key: "write_export_db", icon: Database, kind: "db" },
    {
      key: "burn_captions", icon: Type, kind: "media",
      run: "conditional",
      trigger: "when the cut has dialogue or captions to burn",
    },
    {
      key: "mix_audio", icon: SlidersHorizontal, kind: "media",
      run: "conditional",
      trigger: "when there are voices or music to mix under the picture",
    },
  ],
};

export const TOOL_KIND_COPY: Record<ToolSpec["kind"], string> = {
  llm: "model call",
  db: "database write",
  validator: "validation",
  media: "media pipeline",
  service: "service",
};

/** short badge under an idle node that won't run by itself */
export const TOOL_RUN_HINT: Record<NonNullable<ToolSpec["run"]>, string> = {
  conditional: "if needed",
  "on-demand": "optional",
};

/** The icon for a dynamically-discovered tool (emitted but not in the spec). */
export const FALLBACK_TOOL_ICON: LucideIcon = Sparkles;
