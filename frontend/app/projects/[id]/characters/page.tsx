"use client";

import { Button } from "@/components/ui/button";
import { CharacterList } from "@/components/characters/CharacterList";
import { useCharacters, useExtractCharacters } from "@/hooks/useCharacters";

export default function CharactersPage({
  params,
}: {
  params: { id: string };
}) {
  const { data, isLoading } = useCharacters(params.id);
  const extractCharacters = useExtractCharacters();

  const characters = data?.characters || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Characters</h1>
        <Button
          onClick={() => extractCharacters.mutate(params.id)}
          disabled={extractCharacters.isPending}
        >
          {extractCharacters.isPending
            ? "Extracting with Qwen-Max..."
            : "Extract from Script"}
        </Button>
      </div>
      {extractCharacters.isError && (
        <p className="text-sm text-destructive">
          Error: {(extractCharacters.error as Error).message}
        </p>
      )}
      {isLoading ? (
        <p className="text-muted-foreground">Loading characters...</p>
      ) : (
        <CharacterList characters={characters} />
      )}
    </div>
  );
}
