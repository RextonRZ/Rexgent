import { create } from "zustand";
import type { GeneratedClip } from "@/lib/types";

interface EditState {
  selectedClip: GeneratedClip | null;
  setSelectedClip: (clip: GeneratedClip | null) => void;
}

export const useEditStore = create<EditState>((set) => ({
  selectedClip: null,
  setSelectedClip: (clip) => set({ selectedClip: clip }),
}));
