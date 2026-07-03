"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CharacterList } from "@/components/characters/CharacterList";
import { RelationshipGraph } from "@/components/characters/RelationshipGraph";
import { RelationshipEdgePanel } from "@/components/characters/RelationshipEdgePanel";
import { SceneGraph } from "@/components/characters/SceneGraph";
import { NarrativeGraphView } from "@/components/agents/NarrativeGraphView";
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
  const [inferMbti, setInferMbti] = useState(false);

  const characters = data?.characters || [];

  const castingByCharId = useMemo(() => {
    const map: Record<string, CastingCharacter> = {};
    (bible?.characters || []).forEach((c) => (map[c.id] = c));
    return map;
  }, [bible]);

  const characterNames = useMemo(() => {
    const map: Record<string, string> = {};
    (graph?.characters || []).forEach((c) => (map[c.id] = c.name));
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
          <Button
            variant="secondary"
            onClick={() => runCasting.mutate()}
            disabled={runCasting.isPending}
            title="Generate costume, location & style plates for the whole cast"
          >
            {runCasting.isPending ? "Generating…" : "Generate Plates"}
          </Button>
        </div>
      </div>

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
          <TabsTrigger value="scenes">Scenes</TabsTrigger>
          <TabsTrigger value="graph">Story graph</TabsTrigger>
        </TabsList>
        <TabsContent value="cards">
          {isLoading ? (
            <p className="text-muted-foreground">Loading characters...</p>
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
        <TabsContent value="scenes">
          <SceneGraph
            scenes={graph?.scenes || []}
            characters={graph?.characters || []}
          />
        </TabsContent>
        <TabsContent value="graph">
          <NarrativeGraphView projectId={params.id} />
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
