"use client";

import { Button } from "@/components/ui/button";
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
    setTimeout(() => download.refetch(), 3000);
  };

  const d = download.data;
  const report = d?.report_json;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* final cut */}
      <div className="glass rounded-xl p-5 space-y-4">
        <h2 className="font-semibold">Final cut</h2>
        {d?.download_url ? (
          // eslint-disable-next-line jsx-a11y/media-has-caption
          <video
            src={d.download_url}
            className="w-full rounded-lg"
            controls
            preload="metadata"
          />
        ) : (
          <div className="aspect-video rounded-lg bg-secondary flex items-center justify-center text-sm text-muted-foreground">
            Render to preview your drama
          </div>
        )}
        <div className="flex flex-col gap-2">
          <Button
            onClick={handleRender}
            disabled={!jobId || renderExport.isPending}
            className="glow"
          >
            {renderExport.isPending ? "Rendering…" : "🎬 Render final cut"}
          </Button>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              className="flex-1"
              onClick={() => download.refetch()}
            >
              Refresh
            </Button>
            {d?.download_url && (
              <a href={d.download_url} download className="flex-1">
                <Button variant="secondary" className="w-full">
                  Download MP4
                </Button>
              </a>
            )}
          </div>
          {d?.caption_url && (
            <a href={d.caption_url} download>
              <Button variant="ghost" size="sm" className="w-full">
                Download captions (.srt)
              </Button>
            </a>
          )}
        </div>
      </div>

      {/* production report */}
      <div className="glass rounded-xl p-5 space-y-4">
        <h2 className="font-semibold">Production report</h2>
        {report ? (
          <>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <Stat label="Duration" value={`${report.total_duration_seconds}s`} />
              <Stat label="Clips" value={`${report.total_clips}`} />
              <Stat
                label="LLM tokens"
                value={`${(
                  (report.qwen_max_input_tokens || 0) +
                  (report.qwen_max_output_tokens || 0)
                ).toLocaleString()}`}
              />
              <Stat
                label="Total cost"
                value={`$${report.grand_total_cost?.toFixed?.(2) ?? "0.00"} / $40`}
              />
            </div>

            <div className="space-y-2 border-t hairline pt-3">
              <Check
                ok={(report.consistency_pass_rate ?? 0) >= 0.6}
                label="Identity consistency"
                detail={`${((report.consistency_pass_rate ?? 0) * 100).toFixed(0)}% match across clips`}
              />
              <Check
                ok={!!report.within_budget}
                label="Budget alignment"
                detail={
                  report.within_budget
                    ? "Within voucher limit"
                    : "Exceeds voucher"
                }
              />
              <Check
                ok
                label="Captions"
                detail="Generated from script dialogue"
              />
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            Render the final cut to generate the cost &amp; consistency audit.
          </p>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-background/40 p-2.5">
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className="font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function Check({
  ok,
  label,
  detail,
}: {
  ok: boolean;
  label: string;
  detail: string;
}) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span
        className={`flex h-5 w-5 items-center justify-center rounded-full text-[11px] ${
          ok ? "bg-ok/15 text-ok" : "bg-bad/15 text-bad"
        }`}
      >
        {ok ? "✓" : "✕"}
      </span>
      <span className="font-medium">{label}</span>
      <span className="text-muted-foreground text-xs ml-auto">{detail}</span>
    </div>
  );
}
