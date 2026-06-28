import { create } from "zustand";

interface ProjectState {
  currentProjectId: string | null;
  currentScriptId: string | null;
  setCurrentProjectId: (id: string) => void;
  setCurrentScriptId: (id: string) => void;
}

export const useProjectStore = create<ProjectState>((set) => ({
  currentProjectId: null,
  currentScriptId: null,
  setCurrentProjectId: (id) => set({ currentProjectId: id }),
  setCurrentScriptId: (id) => set({ currentScriptId: id }),
}));
