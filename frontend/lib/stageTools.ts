import {
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
  Mic,
  PenLine,
  RefreshCw,
  ScanFace,
  Scissors,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Timer,
  Type,
  Upload,
  Users,
  Volume2,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import type { StageKey } from "@/hooks/useLiveRun";

/** ── the crew workflow topology ──────────────────────────────────────────
 * The FIXED set of tools each stage orchestrates, mirroring what the backend
 * actually instruments (app/websocket/tool_events.py call sites). Idle nodes
 * render faint from this list before any event arrives; live `tools` state
 * from useLiveRunStore overlays running/done/failed per node. A tool the
 * backend emits that isn't listed here still renders (appended dynamically),
 * so the graph can never hide real machinery.
 */
export interface ToolSpec {
  key: string;
  icon: LucideIcon;
  /** what kind of node this is — shapes the tooltip copy */
  kind: "llm" | "db" | "validator" | "media" | "service";
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
    { key: "llm_write", icon: Sparkles, kind: "llm" },
    { key: "narrative_judge", icon: Scale, kind: "validator" },
    { key: "plot_gap_check", icon: Search, kind: "validator" },
    { key: "ending_lab", icon: GitBranch, kind: "llm" },
    { key: "structure_scenes", icon: ListTree, kind: "llm" },
    { key: "write_script_db", icon: Database, kind: "db" },
  ],
  characters: [
    { key: "extract_cast", icon: Users, kind: "llm" },
    { key: "map_relationships", icon: Share2, kind: "llm" },
    { key: "generate_plates", icon: Image, kind: "media" },
    { key: "face_lock", icon: ScanFace, kind: "validator" },
    { key: "voice_assign", icon: Mic, kind: "service" },
    { key: "write_cast_db", icon: Database, kind: "db" },
  ],
  storyboard: [
    { key: "shot_breakdown", icon: Clapperboard, kind: "llm" },
    { key: "set_design", icon: Lamp, kind: "llm" },
    { key: "write_shots_db", icon: Database, kind: "db" },
  ],
  generate: [
    { key: "budget_allocate", icon: Wallet, kind: "service" },
    { key: "synth_voices", icon: Volume2, kind: "media" },
    { key: "fit_durations", icon: Timer, kind: "service" },
    { key: "prompt_craft", icon: Wand2, kind: "llm" },
    { key: "dispatch_video", icon: Film, kind: "media" },
    { key: "verify_face", icon: ShieldCheck, kind: "validator" },
    { key: "self_correct", icon: RefreshCw, kind: "service" },
    { key: "write_clip_db", icon: Database, kind: "db" },
  ],
  export: [
    { key: "synth_voices", icon: Volume2, kind: "media" },
    { key: "assemble_timeline", icon: ListTree, kind: "service" },
    { key: "stitch_clips", icon: Film, kind: "media" },
    { key: "burn_captions", icon: Type, kind: "media" },
    { key: "mix_audio", icon: SlidersHorizontal, kind: "media" },
    { key: "render_mp4", icon: Upload, kind: "media" },
    { key: "write_export_db", icon: Database, kind: "db" },
  ],
};

export const TOOL_KIND_COPY: Record<ToolSpec["kind"], string> = {
  llm: "model call",
  db: "database write",
  validator: "validation",
  media: "media pipeline",
  service: "service",
};

/** The icon for a dynamically-discovered tool (emitted but not in the spec). */
export const FALLBACK_TOOL_ICON: LucideIcon = Sparkles;
