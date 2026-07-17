"use client";

import { PawPrint } from "lucide-react";
import { CharacterCard } from "./CharacterCard";
import type { CastingCharacter } from "@/hooks/useCasting";
import type { Character } from "@/lib/types";

export function CharacterList({
  characters,
  castingByCharId,
  voiceEnabled = false,
}: {
  characters: Character[];
  castingByCharId?: Record<string, CastingCharacter>;
  voiceEnabled?: boolean;
}) {
  if (characters.length === 0) {
    return (
      <p className="text-center text-muted-foreground py-8">
        No characters extracted yet.
      </p>
    );
  }

  // animals and creatures get their own section: no voice design, and their
  // plates are identity references rather than costumes
  const humans = characters.filter((c) => !castingByCharId?.[c.id]?.creature);
  const creatures = characters.filter((c) => castingByCharId?.[c.id]?.creature);

  const grid = (list: Character[]) => {
    // 1-2 characters fill the row (no orphan gap); 3+ pack three per row
    const cols =
      list.length <= 2
        ? "grid-cols-1 md:grid-cols-2"
        : "grid-cols-1 md:grid-cols-2 lg:grid-cols-3";
    return (
      <div className={`grid ${cols} gap-4 items-start`}>
        {list.map((char) => (
          <CharacterCard
            key={char.id}
            character={char}
            casting={castingByCharId?.[char.id]}
            voiceEnabled={voiceEnabled}
          />
        ))}
      </div>
    );
  };

  if (creatures.length === 0) return grid(humans);

  return (
    <div className="space-y-6">
      {humans.length > 0 && grid(humans)}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <PawPrint className="size-3.5 text-muted-foreground" />
          <p className="text-xs uppercase tracking-widest text-muted-foreground">
            Animals &amp; creatures
          </p>
        </div>
        <p className="text-[11px] text-muted-foreground">
          Non human cast: their plates are identity references (species,
          markings, collar) instead of costumes, faces are not ArcFace
          verified, and no voice is designed unless they speak.
        </p>
        {grid(creatures)}
      </div>
    </div>
  );
}
