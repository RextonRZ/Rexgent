import { create } from "zustand";

export interface ClipProgress {
  shot_id: string;
  status:
    | "PENDING"
    | "GENERATING"
    | "CHECKING"
    | "APPROVED"
    | "NEEDS_REVIEW"
    | "FAILED";
  model?: string;
  clip_url?: string;
  consistency_score?: number | null;
  retry_number?: number;
  reason?: string;
}

interface GenerationState {
  clips: Record<string, ClipProgress>;
  currentCost: number;
  budgetRemaining: number;
  jobComplete: boolean;
  reset: () => void;
  upsertClip: (shotId: string, data: Partial<ClipProgress>) => void;
  setCost: (current: number, remaining: number) => void;
  setComplete: (v: boolean) => void;
}

export const useGenerationStore = create<GenerationState>((set) => ({
  clips: {},
  currentCost: 0,
  budgetRemaining: 34,
  jobComplete: false,
  reset: () =>
    set({ clips: {}, currentCost: 0, budgetRemaining: 34, jobComplete: false }),
  upsertClip: (shotId, data) =>
    set((state) => ({
      clips: {
        ...state.clips,
        [shotId]: {
          ...state.clips[shotId],
          ...data,
          shot_id: shotId,
          status: data.status ?? state.clips[shotId]?.status ?? "PENDING",
        },
      },
    })),
  setCost: (current, remaining) =>
    set({ currentCost: current, budgetRemaining: remaining }),
  setComplete: (v) => set({ jobComplete: v }),
}));
