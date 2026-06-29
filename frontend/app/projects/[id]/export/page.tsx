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
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Export</h1>
      <ExportPanel projectId={params.id} jobId={jobId} />
    </div>
  );
}
