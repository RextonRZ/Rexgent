import { create } from "zustand";

interface CharacterState {
  selectedCharacterId: string | null;
  setSelectedCharacterId: (id: string | null) => void;
}

export const useCharacterStore = create<CharacterState>((set) => ({
  selectedCharacterId: null,
  setSelectedCharacterId: (id) => set({ selectedCharacterId: id }),
}));
