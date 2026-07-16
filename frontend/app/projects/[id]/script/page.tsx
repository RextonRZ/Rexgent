"use client";

import { useEffect, useRef, useState } from "react";
import { NextStepButton } from "@/components/shared/NextStepButton";
import { useSearchParams } from "next/navigation";
import { useProject } from "@/hooks/useProjects";
import { useGenerateScript, useLatestScript } from "@/hooks/useScript";
import { ScriptImport } from "@/components/script/ScriptImport";
import { ScriptEditor } from "@/components/script/ScriptEditor";
import { BeatSheet } from "@/components/script/BeatSheet";
import { PlotGapPanel } from "@/components/script/PlotGapPanel";
import { EndingGraph } from "@/components/script/EndingGraph";
import {
  NarrativeJudgeReport,
  type JudgeResult,
} from "@/components/script/NarrativeJudgeReport";
import { AutoRunPanel } from "@/components/agent/AutoRunPanel";
import { PageHeader } from "@/components/shared/PageHeader";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useAnalyzeScript,
  useJudgeScript,
  useDismissFlag,
  type AnalysisResult,
} from "@/hooks/usePlotAnalysis";

export default function ScriptPage({ params }: { params: { id: string } }) {
  const searchParams = useSearchParams();
  const { data: project } = useProject(params.id);
  // scope budgeted in the create modal: URL params right after creation,
  // the project's stored scope on any later visit
  const epParam =
    Number(searchParams.get("ep")) || project?.episode_count || undefined;
  const lenParam =
    Number(searchParams.get("len")) || project?.target_length || undefined;
  const projectPremise = project?.premise ?? "";
  const projectGenre = project?.genre ?? "";

  const [scriptData, setScriptData] = useState<{
    script_id: string;
    raw_text: string;
  } | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [judgement, setJudgement] = useState<JudgeResult | null>(null);
  const [rewriteOpen, setRewriteOpen] = useState(false);

  // Resume an existing project straight into the editor instead of the blank
  // "write a script" tabs. (404 for a brand-new project just leaves scriptData null.)
  // When a NEWER draft lands (a rewrite finished — even one whose HTTP response
  // was lost mid-flight), adopt it and clear the old draft's stale critique.
  const { data: latestScript } = useLatestScript(params.id);
  useEffect(() => {
    if (!latestScript?.id) return;
    if (!scriptData) {
      setScriptData({
        script_id: latestScript.id,
        raw_text: latestScript.raw_text ?? "",
      });
    } else if (latestScript.id !== scriptData.script_id) {
      setScriptData({
        script_id: latestScript.id,
        raw_text: latestScript.raw_text ?? "",
      });
      setJudgement(null);
      setAnalysis(null);
      judgedTextRef.current = null;
      analyzedTextRef.current = null;
    }
  }, [latestScript, scriptData]);

  const analyzeScript = useAnalyzeScript();
  const judgeScript = useJudgeScript();
  const dismissFlag = useDismissFlag();
  const generateScript = useGenerateScript();

  // a rejected verdict is an ACTION, not a verdict to live with: rewrite the
  // draft with the judge's own critique as revision notes. The old version
  // stays in history; the stale report clears because it graded the old text.
  const [rewriteError, setRewriteError] = useState<string | null>(null);
  const handleRewrite = async () => {
    if (!judgement || !scriptData) return;
    setRewriteError(null);
    const points = [
      ...judgement.blocking_issues,
      ...judgement.top_weaknesses,
    ].slice(0, 6);
    const notes =
      "REVISION PASS. The previous draft was rejected by the script judge. " +
      "Fix these specific problems while keeping what worked:\n- " +
      points.join("\n- ") +
      (judgement.judge_summary
        ? `\nJudge summary: ${judgement.judge_summary}`
        : "");
    try {
      const data = await generateScript.mutateAsync({
        project_id: params.id,
        premise: projectPremise || scriptData.raw_text.slice(0, 280),
        genre: projectGenre || "drama",
        episode_count: epParam,
        target_length: lenParam,
        notes,
      });
      setScriptData({ script_id: data.script_id, raw_text: data.raw_text });
      setJudgement(null);
      setAnalysis(null);
      judgedTextRef.current = null;
      analyzedTextRef.current = null;
    } catch {
      // the request can die while the crew keeps writing server side; the
      // editor self-heals over the websocket when the new draft lands
      setRewriteError(
        "The connection dropped. If the crew was still writing, the editor refreshes itself when the new draft lands; watch the dock."
      );
    }
  };

  // Skip pointless re-runs: only call the LLM again if the text changed since
  // the last analysis/judgement.
  const currentTextRef = useRef<string>("");
  const analyzedTextRef = useRef<string | null>(null);
  const judgedTextRef = useRef<string | null>(null);

  const handleAnalyze = async () => {
    if (!scriptData) return;
    const text = currentTextRef.current || scriptData.raw_text;
    if (analysis && analyzedTextRef.current === text) return; // unchanged
    const result = await analyzeScript.mutateAsync(scriptData.script_id);
    analyzedTextRef.current = text;
    setAnalysis(result);
  };

  const handleJudge = async () => {
    if (!scriptData) return;
    const text = currentTextRef.current || scriptData.raw_text;
    if (judgement && judgedTextRef.current === text) return; // unchanged
    const result = await judgeScript.mutateAsync(scriptData.script_id);
    judgedTextRef.current = text;
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
      <PageHeader
        title="Script"
        sub="Write it, then let the AI critique it before a cent is spent on video."
      />

      {!scriptData ? (
        <div className="max-w-4xl">
          <Tabs defaultValue="auto">
            <TabsList>
              <TabsTrigger value="auto">Full Auto</TabsTrigger>
              <TabsTrigger value="import">Import Script</TabsTrigger>
            </TabsList>
            <TabsContent value="auto">
              <AutoRunPanel
                projectId={params.id}
                initialPremise={projectPremise}
                initialGenre={projectGenre}
                initialEpisodes={epParam}
                initialTargetLength={lenParam}
                onScriptReady={(r) => {
                  // the page flips to the editor (query invalidation refetches
                  // the fresh script); carry the judge's verdict into the
                  // analysis rail so the score is right there beside the text
                  if (!r.judgement) return;
                  const j = r.judgement;
                  setJudgement({
                    scores: j.scores ?? {},
                    overall: j.overall ?? 0,
                    blocking_issues: j.blocking_issues ?? [],
                    top_strengths: j.top_strengths ?? [],
                    top_weaknesses: j.top_weaknesses ?? [],
                    recommendation: (j.recommendation ??
                      "PROCEED") as JudgeResult["recommendation"],
                    judge_summary: j.judge_summary ?? "",
                  });
                }}
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
                  onClick={() => setRewriteOpen(true)}
                  variant="secondary"
                  size="sm"
                >
                  Rewrite script
                </Button>
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
            {latestScript?.structured_json && (
              <BeatSheet structured={latestScript.structured_json} />
            )}
            <ScriptEditor
              key={scriptData.script_id}
              scriptId={scriptData.script_id}
              initialContent={scriptData.raw_text}
              onTextChange={(t) => (currentTextRef.current = t)}
            />
          </div>

          {/* analysis rail */}
          {hasAnalysis && (
            <div className="lg:col-span-2 space-y-4">
              <h2 className="text-sm font-medium text-muted-foreground">
                AI analysis
              </h2>
              {judgement && (
                <>
                  <NarrativeJudgeReport result={judgement} />
                  {judgement.recommendation !== "PROCEED" && (
                    <div className="space-y-1.5">
                      <Button
                        onClick={handleRewrite}
                        disabled={generateScript.isPending}
                        className="w-full"
                        size="sm"
                      >
                        {generateScript.isPending
                          ? "Rewriting with the critique…"
                          : "Rewrite with this critique"}
                      </Button>
                      {rewriteError && (
                        <p className="rounded-lg border border-amber-400/30 bg-amber-500/10 px-2.5 py-1.5 text-[11px] leading-4 text-amber-300">
                          {rewriteError}
                        </p>
                      )}
                      <p className="text-[11px] leading-4 text-muted-foreground">
                        The agent already spent one automatic rewrite on this
                        script. This writes another draft targeting the
                        blocking issues above, a few thousand more tokens;
                        your current version stays in history. Or edit the
                        text yourself for zero tokens and press Score Quality
                        again.
                      </p>
                    </div>
                  )}
                </>
              )}
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

          <Dialog open={rewriteOpen} onOpenChange={setRewriteOpen}>
            <DialogContent className="glass sm:max-w-2xl" showCloseButton>
              <DialogHeader>
                <DialogTitle>Rewrite script</DialogTitle>
              </DialogHeader>
              {/* -mb-4: the scroll region reaches the dialog's bottom edge so
                  the floating submit sits flush with the rounded corner */}
              <DialogBody className="-mb-4">
                <AutoRunPanel
                  projectId={params.id}
                  mode="rewrite"
                  initialPremise={projectPremise}
                  initialGenre={projectGenre}
                  initialEpisodes={epParam}
                  initialTargetLength={lenParam}
                  onRewritten={() => setRewriteOpen(false)}
                />
              </DialogBody>
            </DialogContent>
          </Dialog>
        </div>
      )}
      <NextStepButton projectId={params.id} current="script" />
    </div>
  );
}
