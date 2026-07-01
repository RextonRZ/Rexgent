import { useMutation, useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import type { ProductionReport } from "@/lib/types";

export interface ExportDownload {
  id: string;
  url: string | null;
  duration_seconds: number | null;
  caption_url: string | null;
  report_json: ProductionReport | null;
  download_url: string | null;
}

export function useRenderExport() {
  return useMutation({
    mutationFn: async ({
      projectId,
      jobId,
      clips,
      audioUrl,
      audioVolume,
      audioFadeIn,
      audioFadeOut,
    }: {
      projectId: string;
      jobId: string;
      clips?: {
        clip_id?: string;
        url?: string;
        trim_start: number;
        trim_end: number;
      }[];
      audioUrl?: string | null;
      audioVolume?: number;
      audioFadeIn?: number;
      audioFadeOut?: number;
    }) => {
      const { data } = await api.post("/api/export/render", {
        project_id: projectId,
        job_id: jobId,
        clips,
        audio_url: audioUrl || null,
        audio_volume: audioVolume ?? 1.0,
        audio_fade_in: audioFadeIn ?? 0.0,
        audio_fade_out: audioFadeOut ?? 0.0,
      });
      return data;
    },
  });
}

export function useUploadAudio(projectId: string) {
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post<{ url: string }>(
        `/api/export/${projectId}/audio`,
        form,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      return data;
    },
  });
}

export function useUploadMedia(projectId: string) {
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post<{ url: string }>(
        `/api/export/${projectId}/media`,
        form,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      return data;
    },
  });
}

export function useExportDownload(projectId: string) {
  return useQuery<ExportDownload>({
    queryKey: ["export", projectId],
    queryFn: async () => {
      const { data } = await api.get(`/api/export/${projectId}/download`);
      return data;
    },
    enabled: false,
    retry: false,
  });
}
