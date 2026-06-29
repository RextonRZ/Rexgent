"use client";

import { useState } from "react";
import { ScriptImport } from "@/components/script/ScriptImport";
import { ScriptGenerate } from "@/components/script/ScriptGenerate";
import { ScriptEditor } from "@/components/script/ScriptEditor";
import { PlotGapPanel } from "@/components/script/PlotGapPanel";
import { EndingGraph } from "@/components/script/EndingGraph";
import {
  NarrativeJudgeReport,
  type JudgeResult,
} from "@/components/script/NarrativeJudgeReport";
import { AutoRunPanel } from "@/components/agent/AutoRunPanel";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useAnalyzeScript,
  useJudgeScript,
  useDismissFlag,
  type AnalysisResult,
} from "@/hooks/usePlotAnalysis";

export default function ScriptPage({ params }: { params: { id: string } }) {
  const [scriptData, setScriptData] = useState<{
    script_id: string;
    raw_text: string;
  } | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [judgement, setJudgement] = useState<JudgeResult | null>(null);

  const analyzeScript = useAnalyzeScript();
  const judgeScript = useJudgeScript();
  const dismissFlag = useDismissFlag();

  const handleAnalyze = async () => {
    if (!scriptData) return;
    const result = await analyzeScript.mutateAsync(scriptData.script_id);
    setAnalysis(result);
  };

  const handleJudge = async () => {
    if (!scriptData) return;
    const result = await judgeScript.mutateAsync(scriptData.script_id);
    setJudgement(result);
  };

  const handleDismiss = async (flagId: string) => {
    await dismissFlag.mutateAsync({ flagId, status: "DISMISSED" });
    setAnalysis((prev) =>
      prev
        ? {
            ...prev,
            plot_gaps: {
              ...prev.plot_gaps,
              flags: prev.plot_gaps.flags.map((f) =>
                f.id === flagId ? { ...f, status: "DISMISSED" } : f
              ),
            },
          }
        : prev
    );
  };

  const hasAnalysis = !!analysis || !!judgement;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Script</h1>
        <p className="text-sm text-muted-foreground">
          Write it, then let the AI critique it before a cent is spent on video.
        </p>
      </div>

      {!scriptData ? (
        <div className="max-w-3xl">
          <Tabs defaultValue="auto">
            <TabsList>
              <TabsTrigger value="auto">⚡ Full Auto</TabsTrigger>
              <TabsTrigger value="generate">Write from Scratch</TabsTrigger>
              <TabsTrigger value="import">Import Script</TabsTrigger>
            </TabsList>
            <TabsContent value="auto">
              <AutoRunPanel projectId={params.id} />
            </TabsContent>
            <TabsContent value="generate">
              <ScriptGenerate
                projectId={params.id}
                onSuccess={(data) =>
                  setScriptData({
                    script_id: data.script_id,
                    raw_text: data.raw_text,
                  })
                }
              />
            </TabsContent>
            <TabsContent value="import">
              <ScriptImport
                projectId={params.id}
                onSuccess={(data) =>
                  setScriptData({
                    script_id: data.script_id,
                    raw_text: data.raw_text,
                  })
                }
              />
            </TabsContent>
          </Tabs>
        </div>
      ) : (
        <div className={hasAnalysis ? "grid gap-6 lg:grid-cols-5" : ""}>
          {/* editor */}
          <div className={hasAnalysis ? "lg:col-span-3 space-y-3" : "space-y-3"}>
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium text-muted-foreground">
                Screenplay
              </h2>
              <div className="flex gap-2">
                <Button
                  onClick={handleAnalyze}
                  disabled={analyzeScript.isPending}
                  variant="secondary"
                  size="sm"
                >
                  {analyzeScript.isPending ? "Analyzing…" : "Run AI Analysis"}
                </Button>
                <Button
                  onClick={handleJudge}
                  disabled={judgeScript.isPending}
                  variant="secondary"
                  size="sm"
                >
                  {judgeScript.isPending ? "Judging…" : "Score Quality"}
                </Button>
              </div>
            </div>
            <ScriptEditor
              scriptId={scriptData.script_id}
              initialContent={scriptData.raw_text}
            />
          </div>

          {/* analysis rail */}
          {hasAnalysis && (
            <div className="lg:col-span-2 space-y-4">
              <h2 className="text-sm font-medium text-muted-foreground">
                AI analysis
              </h2>
              {judgement && <NarrativeJudgeReport result={judgement} />}
              {analysis && (
                <>
                  <PlotGapPanel
                    flags={analysis.plot_gaps.flags}
                    onDismiss={handleDismiss}
                  />
                  <EndingGraph
                    hasCompleteEnding={analysis.ending.has_complete_ending}
                    endingQuality={analysis.ending.ending_quality}
                    analysis={analysis.ending.analysis}
                    alternatives={analysis.ending.alternatives}
                  />
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
