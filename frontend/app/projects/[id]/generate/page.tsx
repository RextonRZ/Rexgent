"use client";

import { useWebSocket } from "@/hooks/useWebSocket";
import { NextStepButton } from "@/components/shared/NextStepButton";
import { GenerationLauncher } from "@/components/generate/GenerationLauncher";
import { GenerationQueue } from "@/components/generate/GenerationQueue";
import { PageHeader } from "@/components/shared/PageHeader";
import { TokenDashboard } from "@/components/budget/TokenDashboard";

export default function GeneratePage({ params }: { params: { id: string } }) {
  useWebSocket(params.id);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Generate"
        sub="Watch the studio render your drama, shot by shot."
      />

      {/* the token engineering, front and center */}
      <TokenDashboard projectId={params.id} />

      {/* the dock's Showrunner feed narrates the run — no duplicate here */}
      <GenerationLauncher projectId={params.id} />

      <GenerationQueue projectId={params.id} />
      <NextStepButton projectId={params.id} current="generate" />
    </div>
  );
}
