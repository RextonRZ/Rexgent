"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CharacterList } from "@/components/characters/CharacterList";
import { RelationshipGraph } from "@/components/characters/RelationshipGraph";
import { RelationshipEdgePanel } from "@/components/characters/RelationshipEdgePanel";
import { SceneGraph } from "@/components/characters/SceneGraph";
import { useCharacters, useExtractCharacters } from "@/hooks/useCharacters";
import {
  useGraph,
  useBuildRelationshipGraph,
} from "@/hooks/useRelationshipGraph";
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

  const [selectedEdge, setSelectedEdge] =
    useState<CharacterRelationship | null>(null);
  const [inferMbti, setInferMbti] = useState(false);

  const characters = data?.characters || [];

  const characterNames = useMemo(() => {
    const map: Record<string, string> = {};
    (graph?.characters || []).forEach((c) => (map[c.id] = c.name));
    return map;
  }, [graph]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Characters</h1>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
            <input
              type="checkbox"
              checked={inferMbti}
              onChange={(e) => setInferMbti(e.target.checked)}
            />
            Infer MBTI (for fun)
          </label>
          <Button
            onClick={() =>
              extractCharacters.mutate({ projectId: params.id, inferMbti })
            }
            disabled={extractCharacters.isPending}
          >
            {extractCharacters.isPending
              ? "Extracting..."
              : "Extract from Script"}
          </Button>
          <Button
            variant="secondary"
            onClick={() => buildGraph.mutate(params.id)}
            disabled={buildGraph.isPending}
          >
            {buildGraph.isPending ? "Building..." : "Build Relationships"}
          </Button>
        </div>
      </div>

      <Tabs defaultValue="cards">
        <TabsList>
          <TabsTrigger value="cards">Cards</TabsTrigger>
          <TabsTrigger value="relationships">Relationships</TabsTrigger>
          <TabsTrigger value="scenes">Scenes</TabsTrigger>
        </TabsList>
        <TabsContent value="cards">
          {isLoading ? (
            <p className="text-muted-foreground">Loading characters...</p>
          ) : (
            <CharacterList characters={characters} />
          )}
        </TabsContent>
        <TabsContent value="relationships">
          <RelationshipGraph
            characters={graph?.characters || []}
            relationships={graph?.relationships || []}
            onSelectEdge={setSelectedEdge}
          />
        </TabsContent>
        <TabsContent value="scenes">
          <SceneGraph
            scenes={graph?.scenes || []}
            characters={graph?.characters || []}
          />
        </TabsContent>
      </Tabs>

      <RelationshipEdgePanel
        rel={selectedEdge}
        characterNames={characterNames}
        onClose={() => setSelectedEdge(null)}
      />
    </div>
  );
}
