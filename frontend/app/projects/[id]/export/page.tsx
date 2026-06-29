"use client";

import { useEffect, useState } from "react";
import { ExportPanel } from "@/components/edit/ExportPanel";
import { useLatestJob } from "@/hooks/useGeneration";

export default function ExportPage({ params }: { params: { id: string } }) {
  const latestJob = useLatestJob(params.id);
  const [jobId, setJobId] = useState<string | null>(null);

  useEffect(() => {
    latestJob.refetch().then((res) => {
      if (res.data?.id) setJobId(res.data.id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Export</h1>
        <p className="text-sm text-muted-foreground">
          Stitch the final film and prove the economics.
        </p>
      </div>
      <ExportPanel projectId={params.id} jobId={jobId} />
    </div>
  );
}
