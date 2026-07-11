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

  const [spend, setSpend] = useState<SpendRequest | null>(null);
  const handleGenerate = () =>
    setSpend({
      title: "Generate the storyboard",
      costLine:
        "Boarding costs a few cents of AI writing, and every new location gets a background plate at about $0.08 each.",
      note: "Re-boarding replaces the current shots; locations that already have plates are not repainted.",
      confirmLabel: "Generate storyboard",
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
                  The budget allocates itself once the storyboard exists —
                  it decides which shots get Wan vs HappyHorse under the $40
                  voucher.
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
                      className="aspect-video w-full object-cover"
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
            <NarrativeGraphView projectId={params.id} />
            <SceneGraph
              scenes={graph?.scenes || []}
              characters={graph?.characters || []}
              boardScenes={scenes}
            />
          </div>
        </TabsContent>
      </Tabs>
      <SpendConfirm request={spend} onClose={() => setSpend(null)} />
      <NextStepButton projectId={params.id} current="storyboard" />
    </div>
  );
}
