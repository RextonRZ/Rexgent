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
      audioDuck,
    }: {
      projectId: string;
      jobId: string;
      clips?: {
        clip_id?: string;
        url?: string;
        trim_start: number;
        trim_end: number | null; // null = to the end of the clip
      }[];
      audioUrl?: string | null;
      audioVolume?: number;
      audioFadeIn?: number;
      audioFadeOut?: number;
      audioDuck?: boolean;
    }) => {
      const { data } = await api.post("/api/export/render", {
        project_id: projectId,
        job_id: jobId,
        clips,
        audio_url: audioUrl || null,
        audio_volume: audioVolume ?? 1.0,
        audio_fade_in: audioFadeIn ?? 0.0,
        audio_fade_out: audioFadeOut ?? 0.0,
        audio_duck: audioDuck ?? true,
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

export interface SuggestedTrack {
  id: string;
  title: string;
  url: string | null;
  mood?: string;
  duration?: number | null;
  tempo?: string | null;
  intensity?: number;
}

export interface MusicSuggestion {
  mood: string;
  results: SuggestedTrack[];
}

/** Lazily fetch mood-matched library music for this project (fires on demand,
 *  not on mount, because resolving each track uploads it to shared storage). */
export function useSuggestMusic(projectId: string) {
  return useMutation({
    mutationFn: async (): Promise<MusicSuggestion> => {
      const { data } = await api.get<MusicSuggestion>(
        `/api/assets/music/suggest`,
        { params: { project_id: projectId } }
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
    // fetch on mount so a finished export's download button survives a page
    // refresh (404 while none exists is fine: retry off, data stays empty)
    retry: false,
  });
}
