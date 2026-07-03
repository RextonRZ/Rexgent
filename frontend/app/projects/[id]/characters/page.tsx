"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { NextStepButton } from "@/components/shared/NextStepButton";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CharacterList } from "@/components/characters/CharacterList";
import { RelationshipGraph } from "@/components/characters/RelationshipGraph";
import { RelationshipEdgePanel } from "@/components/characters/RelationshipEdgePanel";
import { Skeleton } from "@/components/shared/Skeleton";
import { useCharacters, useExtractCharacters } from "@/hooks/useCharacters";
import {
  useGraph,
  useBuildRelationshipGraph,
} from "@/hooks/useRelationshipGraph";
import { useBible, useRunCasting } from "@/hooks/useCasting";
import type { CastingCharacter } from "@/hooks/useCasting";
import type { CharacterRelationship } from "@/lib/types";

export default function CharactersPage({
  params,
}: {
  params: { id: string };
}) {
  const { data, isLoading } = useCharacters(params.id);
  const extractCharacters = useExtractCharacters();
  const { data: graph } = useGraph(params.id);
  const buildGraph = useBuildRelationshipGraph();
  const { data: bible } = useBible(params.id);
  const runCasting = useRunCasting(params.id);

  const [selectedEdge, setSelectedEdge] =
    useState<CharacterRelationship | null>(null);

  const characters = data?.characters || [];

  // Relationships build themselves: once after extraction, and once on load if
  // the cast exists but no relationships do (no button to remember).
  const autoBuilt = useRef(false);
  useEffect(() => {
    if (autoBuilt.current || buildGraph.isPending) return;
    if (
      characters.length >= 2 &&
      graph &&
      (graph.relationships?.length ?? 0) === 0
    ) {
      autoBuilt.current = true;
      buildGraph.mutate(params.id);
    }
  }, [characters.length, graph, buildGraph, params.id]);

  const handleExtract = () =>
    extractCharacters.mutate(
      { projectId: params.id },
      {
        onSuccess: () => {
          autoBuilt.current = true;
          buildGraph.mutate(params.id);
        },
      }
    );

  const castingByCharId = useMemo(() => {
    const map: Record<string, CastingCharacter> = {};
    (bible?.characters || []).forEach((c) => (map[c.id] = c));
    return map;
  }, [bible]);

  const characterById = useMemo(() => {
    const map: Record<string, { name: string; image?: string | null }> = {};
    (graph?.characters || []).forEach(
      (c) => (map[c.id] = { name: c.name, image: c.reference_image_url })
    );
    return map;
  }, [graph]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Characters</h1>
          <p className="text-sm text-muted-foreground">
            Build the cast and lock each face before generating.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button onClick={handleExtract} disabled={extractCharacters.isPending}>
            {extractCharacters.isPending
              ? "Extracting..."
              : "Extract from Script"}
          </Button>
          <Button
            variant="outline"
            onClick={() => runCasting.mutate()}
            disabled={runCasting.isPending}
            title="Generate costume, location & style plates for the whole cast"
          >
            {runCasting.isPending ? "Generating…" : "Generate Plates"}
          </Button>
        </div>
      </div>

      {buildGraph.isPending && (
        <p className="text-xs text-muted-foreground">
          Building character relationships…
        </p>
      )}
      {runCasting.isSuccess && (
        <p className="text-xs text-muted-foreground">
          Plate generation started — costume plates and voices will appear on each
          card as they finish. Review locations, style, and approve on the{" "}
          <span className="text-primary">Generate</span> step.
        </p>
      )}

      <Tabs defaultValue="cards">
        <TabsList>
          <TabsTrigger value="cards">Cards</TabsTrigger>
          <TabsTrigger value="relationships">Relationships</TabsTrigger>
        </TabsList>
        <TabsContent value="cards">
          {isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-64 rounded-xl" />
              ))}
            </div>
          ) : (
            <CharacterList
              characters={characters}
              castingByCharId={castingByCharId}
            />
          )}
        </TabsContent>
        <TabsContent value="relationships">
          <RelationshipGraph
            characters={graph?.characters || []}
            relationships={graph?.relationships || []}
            onSelectEdge={setSelectedEdge}
          />
        </TabsContent>
      </Tabs>

      <RelationshipEdgePanel
        rel={selectedEdge}
        characterById={characterById}
        onClose={() => setSelectedEdge(null)}
      />
      <NextStepButton projectId={params.id} current="characters" />
    </div>
  );
}
