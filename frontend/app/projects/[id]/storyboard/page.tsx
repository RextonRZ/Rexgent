"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { NextStepButton } from "@/components/shared/NextStepButton";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/EmptyState";
import { LiveStageStrip } from "@/components/shared/LiveStageStrip";
import { PageHeader } from "@/components/shared/PageHeader";
import { SpendConfirm, type SpendRequest } from "@/components/shared/SpendConfirm";
import { Skeleton } from "@/components/shared/Skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StoryboardView } from "@/components/storyboard/StoryboardView";
import type { SceneLocation } from "@/components/storyboard/SceneSection";
import { BudgetDashboard } from "@/components/storyboard/BudgetDashboard";
import { NarrativeGraphView } from "@/components/agents/NarrativeGraphView";
import { SceneGraph } from "@/components/characters/SceneGraph";
import { useStoryboard, useGenerateStoryboard } from "@/hooks/useStoryboard";
import { useGraph } from "@/hooks/useRelationshipGraph";
import { useBible } from "@/hooks/useCasting";
import { useCalculateBudget, type BudgetResult } from "@/hooks/useBudget";

export default function StoryboardPage({
  params,
}: {
  params: { id: string };
}) {
  const { data, isLoading, refetch } = useStoryboard(params.id);
  const generateStoryboard = useGenerateStoryboard();
  const calculateBudget = useCalculateBudget();
  const { data: graph } = useGraph(params.id);
  const { data: bible } = useBible(params.id);
  const [budget, setBudget] = useState<BudgetResult | null>(null);

  const scenes = data?.scenes || [];

  // scene number -> its location plate, shown to the left of the scene's shots
  const locationByScene = useMemo(() => {
    const map: Record<number, SceneLocation> = {};
    (bible?.locations ?? []).forEach((l) => {
      (l.scene_numbers ?? []).forEach((n) => {
        if (!map[n]) {
          map[n] = {
            url: l.plate_image_url,
            label: l.description || l.location_key.replace(/_/g, " "),
          };
        }
      });
    });
    return map;
  }, [bible]);

  // Budget allocates itself once shots exist — no button to remember.
  const autoBudgeted = useRef(false);
  const hasShots = scenes.some((s) => s.shots.length > 0);

  // Deleting or adding a shot invalidates the allocation: the panel kept
  // pricing the OLD board (a deleted Wan shot stayed counted, while the
  // dissolved beat's survivor re-badged HappyHorse on the left). When the
  // set of shot ids changes, drop the stale plan and re-allocate.
  const shotsSig = useMemo(
    () => scenes.map((s) => s.shots.map((sh) => sh.id).join(",")).join("|"),
    [scenes]
  );
  const prevSig = useRef(shotsSig);
  useEffect(() => {
    if (prevSig.current === shotsSig) return;
    prevSig.current = shotsSig;
    if (budget) {
      setBudget(null);
      autoBudgeted.current = false; // the effect below re-allocates
    }
  }, [shotsSig, budget]);
  useEffect(() => {
    if (autoBudgeted.current || calculateBudget.isPending || !hasShots || budget)
      return;
    autoBudgeted.current = true;
    calculateBudget
      .mutateAsync(params.id)
      .then((result) => {
        setBudget(result);
        refetch();
      })
      .catch(() => {
        autoBudgeted.current = false; // retry on next change
      });
  }, [hasShots, budget, calculateBudget, params.id, refetch]);

  // episode tabs on the story map (only when the drama has 2+ episodes)
  const mapEpisodes = useMemo(
    () => Array.from(new Set(scenes.map((s) => s.episode ?? 1))).sort((a, b) => a - b),
    [scenes]
  );
  const [mapEp, setMapEp] = useState<number | null>(null);
  const activeMapEp = mapEp ?? mapEpisodes[0] ?? 1;
  const mapBoardScenes = useMemo(
    () => (mapEpisodes.length > 1
      ? scenes.filter((s) => (s.episode ?? 1) === activeMapEp)
      : scenes),
    [scenes, mapEpisodes, activeMapEp]
  );
  const mapGraphScenes = useMemo(() => {
    const all = graph?.scenes || [];
    if (mapEpisodes.length <= 1) return all;
    const nums = new Set(mapBoardScenes.map((s) => s.scene_number));
    return all.filter((s) => nums.has(s.number));
  }, [graph, mapBoardScenes, mapEpisodes]);

  const [spend, setSpend] = useState<SpendRequest | null>(null);
  const handleGenerate = () =>
    setSpend({
      title: "Generate the storyboard",
      costLine: "Prices below are estimates. Re-boarding replaces the current shots.",
      note: "Locations that already have plates are not repainted, so re-boarding usually costs less.",
      confirmLabel: "Generate storyboard",
      breakdown: [
        {
          label: "Shot writing",
          detail: "qwen-max directs the shots, qwen-plus and qwen-flash structure them, a few cents of tokens",
          amount: 0.05,
        },
        {
          label: "Location plates",
          detail: "about 3 new locations at $0.08 each on wan2.6-t2i",
          amount: 3 * 0.08,
        },
      ],
      run: () =>
        generateStoryboard.mutate(params.id, {
          onSuccess: () => {
            // new board -> re-allocate
            setBudget(null);
            autoBudgeted.current = false;
          },
        }),
    });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Storyboard"
        sub="Shot-by-shot breakdown, story map, and the world your drama lives in."
      >
        <Button onClick={handleGenerate} disabled={generateStoryboard.isPending}>
          {generateStoryboard.isPending ? "Directing…" : "Generate storyboard"}
        </Button>
      </PageHeader>

      <LiveStageStrip
        projectId={params.id}
        stage="storyboard"
        pending={generateStoryboard.isPending}
        fallback={[
          "Breaking the script into shots",
          "Staging each scene",
          "Set dressing the world",
          "Long scripts take a few minutes",
        ]}
      />

      {generateStoryboard.isError && (
        <p className="text-sm text-bad">
          Error:{" "}
          {(
            generateStoryboard.error as {
              response?: { data?: { detail?: string } };
            }
          )?.response?.data?.detail ??
            (generateStoryboard.error as Error).message}
        </p>
      )}

      <Tabs defaultValue="shots">
        <TabsList>
          <TabsTrigger value="shots">Shots</TabsTrigger>
          <TabsTrigger value="map">Story map</TabsTrigger>
        </TabsList>

        <TabsContent value="shots">
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              {isLoading ? (
                <Skeleton className="h-64 rounded-2xl" />
              ) : !hasShots && !generateStoryboard.isPending ? (
                <EmptyState
                  icon="🎬"
                  title="No storyboard yet"
                  line="The director breaks your script into shots: framing, blocking, lighting and the set every scene must keep. Generate it to see your drama shot by shot."
                >
                  <Button onClick={handleGenerate}>Generate storyboard</Button>
                </EmptyState>
              ) : (
                <StoryboardView
                  scenes={scenes}
                  locationByScene={locationByScene}
                />
              )}
            </div>
            <div className="space-y-4">
              {budget ? (
                <BudgetDashboard
                  budget={budget}
                  projectId={params.id as string}
                  onBudget={setBudget}
                />
              ) : calculateBudget.isPending ? (
                <Skeleton className="h-48 rounded-xl" />
              ) : (
                <div className="rounded-xl border hairline bg-card p-5 text-sm text-muted-foreground">
                  The budget allocates itself once the storyboard exists. It
                  decides which shots render at full quality and which ease to a
                  faster pass under the $40 voucher.
                </div>
              )}

              {bible?.style && (
                <div className="rounded-xl border hairline bg-card overflow-hidden">
                  <div className="px-4 py-2.5 border-b hairline text-xs font-medium">
                    Style
                  </div>
                  {bible.style.plate_image_url && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={bible.style.plate_image_url}
                      alt="Style preset"
                      className="aspect-[3/4] w-full object-cover"
                    />
                  )}
                  <p className="px-4 py-2.5 text-[11px] text-muted-foreground">
                    {bible.style.style_tags.join(", ")}
                  </p>
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="map">
          <div className="space-y-4">
            {mapEpisodes.length > 1 && (
              <div className="flex flex-wrap items-center gap-1.5">
                {mapEpisodes.map((ep) => (
                  <button
                    key={ep}
                    onClick={() => setMapEp(ep)}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                      activeMapEp === ep
                        ? "bg-primary/20 text-primary"
                        : "bg-white/[0.04] text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    Episode {ep}
                  </button>
                ))}
                <span className="ml-2 text-[11px] text-muted-foreground">
                  The story graph and scene flow follow the selected episode.
                </span>
              </div>
            )}
            <NarrativeGraphView
              projectId={params.id}
              sceneNumbers={
                mapEpisodes.length > 1
                  ? mapBoardScenes.map((s) => s.scene_number)
                  : undefined
              }
            />
            <SceneGraph
              scenes={mapGraphScenes}
              characters={graph?.characters || []}
              boardScenes={mapBoardScenes}
            />
          </div>
        </TabsContent>
      </Tabs>
      <SpendConfirm request={spend} onClose={() => setSpend(null)} />
      <NextStepButton projectId={params.id} current="storyboard" />
    </div>
  );
}
