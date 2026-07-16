"use client";

import { useEffect, useMemo, useState } from "react";
import { NextStepButton } from "@/components/shared/NextStepButton";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CharacterList } from "@/components/characters/CharacterList";
import { EmptyState } from "@/components/shared/EmptyState";
import { LiveStageStrip } from "@/components/shared/LiveStageStrip";
import { PageHeader } from "@/components/shared/PageHeader";
import { SpendConfirm, type SpendRequest } from "@/components/shared/SpendConfirm";
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

// projects that already auto-built relationships this session
const autoBuiltProjects = new Set<string>();

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
  const [spend, setSpend] = useState<SpendRequest | null>(null);

  const characters = data?.characters || [];

  // Relationships build themselves: once after extraction, and once on load if
  // the cast exists but no relationships do (no button to remember).
  useEffect(() => {
    // ONE auto-build per project per SESSION — a useRef here resets on every
    // navigation, so a project whose extraction saved zero relationships
    // re-mapped (and re-spent tokens) on every visit to this page.
    if (autoBuiltProjects.has(params.id) || buildGraph.isPending) return;
    if (
      characters.length >= 2 &&
      graph &&
      (graph.relationships?.length ?? 0) === 0
    ) {
      autoBuiltProjects.add(params.id);
      buildGraph.mutate(params.id);
    }
  }, [characters.length, graph, buildGraph, params.id]);

  const handleExtract = () =>
    extractCharacters.mutate(
      { projectId: params.id },
      {
        onSuccess: () => {
          autoBuiltProjects.add(params.id);
          buildGraph.mutate(params.id);
        },
      }
    );

  const castingByCharId = useMemo(() => {
    const map: Record<string, CastingCharacter> = {};
    (bible?.characters || []).forEach((c) => (map[c.id] = c));
    return map;
  }, [bible]);

  // TTS overlay mode: voices are part of the bible, so the spend dialog
  // prices them; in native mode the clips speak for themselves
  const voiceEnabled = Boolean(bible?.tts_overlay);
  const voicelessCount = characters.filter(
    (c) => !castingByCharId[c.id]?.voice_id
  ).length;
  // designed/preset voices can be redesigned; a clone is the user's own
  // recording and is never offered for replacement
  const redesignCount = characters.filter((c) => {
    const cc = castingByCharId[c.id];
    return cc?.voice_id && cc?.voice_source !== "cloned";
  }).length;
  // already painted plates move to an untickable extra: a rerun only charges
  // for the cast members still missing plates unless regenerate is ticked
  const paintedCount = characters.filter((c) =>
    castingByCharId[c.id]?.variants?.some((v) => v.plate_image_url)
  ).length;
  const unpaintedCount = characters.length - paintedCount;

  const characterById = useMemo(() => {
    const map: Record<string, { name: string; image?: string | null }> = {};
    (graph?.characters || []).forEach(
      (c) => (map[c.id] = { name: c.name, image: c.reference_image_url })
    );
    return map;
  }, [graph]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Characters"
        sub="Build the cast and lock each face before generating."
      >
        <Button onClick={handleExtract} disabled={extractCharacters.isPending}>
          {extractCharacters.isPending ? "Extracting…" : "Extract from Script"}
        </Button>
        <Button
          variant="outline"
          onClick={() =>
            setSpend({
              title: "Cast the whole bible",
              costLine: "One run builds the full production bible. Every model it touches is priced below.",
              note: "Estimates: a failed face check can add a retry plate.",
              confirmLabel: "Generate plates",
              breakdown:
                // location plates and the style frame render at storyboard
                // time now, so this run no longer charges for them
                unpaintedCount > 0
                  ? [
                      {
                        label: "Identity and costume plates",
                        detail: `${unpaintedCount} character${unpaintedCount === 1 ? "" : "s"} without plates × 2 each on wan2.6-t2i and qwen-image-edit-max, at $0.075 per image`,
                        amount: unpaintedCount * 2 * 0.075,
                      },
                    ]
                  : undefined,
              options: [
                ...(paintedCount > 0
                  ? [
                      {
                        key: "regenPlates",
                        label: `Regenerate plates for ${paintedCount} already cast character${paintedCount === 1 ? "" : "s"}`,
                        priceLine: `$${(paintedCount * 2 * 0.075).toFixed(2)}`,
                        note: "Repaints their identity and costume plates on the current faces. Leave unticked to keep the plates you have.",
                        defaultOn: false,
                        amount: paintedCount * 2 * 0.075,
                      },
                    ]
                  : []),
                ...(voiceEnabled && voicelessCount > 0
                  ? [
                      {
                        key: "designVoice",
                        label: `Designed voices for ${voicelessCount} character${voicelessCount === 1 ? "" : "s"}`,
                        priceLine: `$${(voicelessCount * 0.2).toFixed(2)}`,
                        note: "qwen-voice-design writes each voice from the character's age and personality, spoken by qwen3-tts-vd. Untick for free presets, and any character can still clone your own voice from the Voice panel on their card.",
                        defaultOn: true,
                        amount: voicelessCount * 0.2,
                      },
                    ]
                  : []),
                ...(voiceEnabled && redesignCount > 0
                  ? [
                      {
                        key: "redesignVoice",
                        label: `Redesign voices for ${redesignCount} character${redesignCount === 1 ? "" : "s"}`,
                        priceLine: `$${(redesignCount * 0.2).toFixed(2)}`,
                        note: "Writes fresh designed voices over their current designed or preset ones. Cloned voices are never touched. Leave unticked to keep what you have.",
                        defaultOn: false,
                        amount: redesignCount * 0.2,
                      },
                    ]
                  : []),
              ],
              run: (choices) =>
                // regenPlates=false still paints anyone missing plates; the
                // tick only decides whether painted ones get redone
                runCasting.mutate({
                  designVoice: choices?.designVoice ?? true,
                  redesignVoice: choices?.redesignVoice ?? false,
                  regenPlates: Boolean(choices?.regenPlates),
                }),
            })
          }
          disabled={runCasting.isPending}
        >
          {runCasting.isPending ? "Generating…" : "Generate Plates"}
        </Button>
      </PageHeader>

      <LiveStageStrip
        projectId={params.id}
        stage="characters"
        pending={extractCharacters.isPending}
        fallback={["Reading the cast from the script", "Profiling each character"]}
      />
      <LiveStageStrip
        projectId={params.id}
        stage="relationships"
        pending={buildGraph.isPending}
        fallback={["Mapping character relationships", "Finding the evidence lines"]}
      />
      {runCasting.isPending && (
        <LiveStageStrip
          projectId={params.id}
          stage="casting"
          pending
          fallback={[
            "Casting the production bible",
            "Painting identity and costume plates",
            "Plates take a minute or two each",
          ]}
        />
      )}
      {runCasting.isSuccess && (
        <p className="text-xs text-muted-foreground">
          Plate generation started. Costume plates{voiceEnabled ? " and voices" : ""} will
          appear on each card as they finish. Review locations, style, and
          approve on the <span className="text-primary">Generate</span> step.
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
          ) : characters.length === 0 && !extractCharacters.isPending ? (
            <EmptyState
              icon="🎭"
              title="No cast yet"
              line="The casting director reads your script and builds a profile for every character: face, wardrobe and personality. Extract them to start casting."
            >
              <Button onClick={handleExtract}>Extract from Script</Button>
            </EmptyState>
          ) : (
            <CharacterList
              characters={characters}
              castingByCharId={castingByCharId}
              voiceEnabled={voiceEnabled}
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
      <SpendConfirm request={spend} onClose={() => setSpend(null)} />
      <NextStepButton projectId={params.id} current="characters" />
    </div>
  );
}
