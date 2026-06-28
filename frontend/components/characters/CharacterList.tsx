"use client";

import { CharacterCard } from "./CharacterCard";
import type { Character } from "@/lib/types";

export function CharacterList({ characters }: { characters: Character[] }) {
  if (characters.length === 0) {
    return (
      <p className="text-center text-muted-foreground py-8">
        No characters extracted yet.
      </p>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {characters.map((char) => (
        <CharacterCard key={char.id} character={char} />
      ))}
    </div>
  );
}
