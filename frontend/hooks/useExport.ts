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
    }: {
      projectId: string;
      jobId: string;
    }) => {
      const { data } = await api.post("/api/export/render", {
        project_id: projectId,
        job_id: jobId,
      });
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
