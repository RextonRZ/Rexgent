"use client";

import { useState } from "react";
import { ScriptImport } from "@/components/script/ScriptImport";
import { ScriptGenerate } from "@/components/script/ScriptGenerate";
import { ScriptEditor } from "@/components/script/ScriptEditor";
import { PlotGapPanel } from "@/components/script/PlotGapPanel";
import { EndingGraph } from "@/components/script/EndingGraph";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useAnalyzeScript,
  useDismissFlag,
  type AnalysisResult,
} from "@/hooks/usePlotAnalysis";

export default function ScriptPage({ params }: { params: { id: string } }) {
  const [scriptData, setScriptData] = useState<{
    script_id: string;
    raw_text: string;
  } | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);

  const analyzeScript = useAnalyzeScript();
  const dismissFlag = useDismissFlag();

  const handleAnalyze = async () => {
    if (!scriptData) return;
    const result = await analyzeScript.mutateAsync(scriptData.script_id);
    setAnalysis(result);
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

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Script</h1>

      {!scriptData ? (
        <Tabs defaultValue="generate">
          <TabsList>
            <TabsTrigger value="generate">Write from Scratch</TabsTrigger>
            <TabsTrigger value="import">Import Script</TabsTrigger>
          </TabsList>
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
      ) : (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Script Editor</h2>
            <Button
              onClick={handleAnalyze}
              disabled={analyzeScript.isPending}
              variant="secondary"
            >
              {analyzeScript.isPending
                ? "Analyzing with Qwen-Max..."
                : "Run AI Analysis"}
            </Button>
          </div>
          <ScriptEditor
            scriptId={scriptData.script_id}
            initialContent={scriptData.raw_text}
          />
          {analysis && (
            <div className="space-y-4">
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
            </div>
          )}
        </div>
      )}
    </div>
  );
}
