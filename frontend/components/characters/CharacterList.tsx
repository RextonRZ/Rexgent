"use client";

import { CharacterCard } from "./CharacterCard";
import type { CastingCharacter } from "@/hooks/useCasting";
import type { Character } from "@/lib/types";

export function CharacterList({
  characters,
  castingByCharId,
}: {
  characters: Character[];
  castingByCharId?: Record<string, CastingCharacter>;
}) {
  if (characters.length === 0) {
    return (
      <p className="text-center text-muted-foreground py-8">
        No characters extracted yet.
      </p>
    );
  }

  // 1-2 characters fill the row (no orphan gap); 3+ pack three per row
  const cols =
    characters.length <= 2
      ? "grid-cols-1 md:grid-cols-2"
      : "grid-cols-1 md:grid-cols-2 lg:grid-cols-3";

  return (
    <div className={`grid ${cols} gap-4 items-start`}>
      {characters.map((char) => (
        <CharacterCard
          key={char.id}
          character={char}
          casting={castingByCharId?.[char.id]}
        />
      ))}
    </div>
  );
}
