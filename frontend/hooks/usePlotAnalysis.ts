import { useMutation } from "@tanstack/react-query";
import api from "@/lib/api";
import type { PlotFlag } from "@/lib/types";
import type { JudgeResult } from "@/components/script/NarrativeJudgeReport";

export interface EndingAlternative {
  id: string;
  title: string;
  summary: string;
  emotional_tone: string;
  compatibility_score: number;
}

export interface AnalysisResult {
  plot_gaps: {
    total_flags: number;
    critical_count: number;
    major_count: number;
    minor_count: number;
    flags: PlotFlag[];
  };
  ending: {
    has_complete_ending: boolean;
    ending_quality: string;
    analysis: {
      main_conflict_resolved: boolean;
      protagonist_arc_complete: boolean;
      emotional_payoff: string;
      open_threads: string[];
    };
    alternatives: EndingAlternative[];
  };
}

export function useAnalyzeScript() {
  return useMutation({
    mutationFn: async (scriptId: string) => {
      const { data } = await api.post<AnalysisResult>(
        `/api/script/${scriptId}/analyze`
      );
      return data;
    },
  });
}

export function useJudgeScript() {
  return useMutation({
    mutationFn: async (scriptId: string) => {
      const { data } = await api.post<JudgeResult>(
        `/api/script/${scriptId}/judge`
      );
      return data;
    },
  });
}

export function useDismissFlag() {
  return useMutation({
    mutationFn: async ({
      flagId,
      status,
    }: {
      flagId: string;
      status: "ACKNOWLEDGED" | "FIXED" | "DISMISSED";
    }) => {
      const { data } = await api.patch(`/api/script/flags/${flagId}`, {
        status,
      });
      return data;
    },
  });
}
