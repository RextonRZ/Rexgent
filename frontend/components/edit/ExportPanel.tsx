"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useRenderExport, useExportDownload } from "@/hooks/useExport";

export function ExportPanel({
  projectId,
  jobId,
}: {
  projectId: string;
  jobId: string | null;
}) {
  const renderExport = useRenderExport();
  const download = useExportDownload(projectId);

  const handleRender = async () => {
    if (!jobId) return;
    await renderExport.mutateAsync({ projectId, jobId });
    // Poll once after a short delay; user can also click Refresh.
    setTimeout(() => download.refetch(), 3000);
  };

  const report = download.data?.report_json;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Export</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Button
          onClick={handleRender}
          disabled={!jobId || renderExport.isPending}
          className="w-full"
        >
          {renderExport.isPending ? "Rendering..." : "Render Final Video"}
        </Button>
        <Button
          variant="outline"
          onClick={() => download.refetch()}
          className="w-full"
        >
          Check for Export
        </Button>

        {download.data?.download_url && (
          <a href={download.data.download_url} download className="block">
            <Button variant="secondary" className="w-full">
              Download MP4
            </Button>
          </a>
        )}
        {download.data?.caption_url && (
          <a href={download.data.caption_url} download className="block">
            <Button variant="ghost" size="sm" className="w-full">
              Download captions (.srt)
            </Button>
          </a>
        )}

        {report && (
          <div className="text-xs text-muted-foreground space-y-1 border-t pt-2">
            <p className="font-medium text-foreground">Production Report</p>
            <p>Duration: {report.total_duration_seconds}s · {report.total_clips} clips</p>
            <p>
              Video: ${report.video_cost_usd?.toFixed?.(2) ?? "0.00"} · LLM: $
              {report.llm_cost_usd?.toFixed?.(2) ?? "0.00"} · Total: $
              {report.grand_total_cost?.toFixed?.(2) ?? "0.00"} / $40
            </p>
            <p>
              Consistency pass rate:{" "}
              {((report.consistency_pass_rate ?? 0) * 100).toFixed(0)}%
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
