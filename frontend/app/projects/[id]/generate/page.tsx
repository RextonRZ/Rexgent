"use client";

import { useWebSocket } from "@/hooks/useWebSocket";
import { NextStepButton } from "@/components/shared/NextStepButton";
import { GenerationLauncher } from "@/components/generate/GenerationLauncher";
import { GenerationQueue } from "@/components/generate/GenerationQueue";
import { ActivityFeed } from "@/components/casting/ActivityFeed";
import { ClarificationModal } from "@/components/agents/ClarificationModal";
import { TokenDashboard } from "@/components/budget/TokenDashboard";

export default function GeneratePage({ params }: { params: { id: string } }) {
  useWebSocket(params.id);

  return (
    <div className="space-y-6">
      <ClarificationModal projectId={params.id} />

      <div>
        <h1 className="text-2xl font-bold tracking-tight">Generate</h1>
        <p className="text-sm text-muted-foreground">
          Watch the studio render your drama, shot by shot.
        </p>
      </div>

      {/* the token engineering, front and center */}
      <TokenDashboard projectId={params.id} />

      {/* launcher (left) beside the activity feed (right) */}
      <div className="grid gap-6 lg:grid-cols-3 items-start">
        <div className="lg:col-span-2">
          <GenerationLauncher projectId={params.id} />
        </div>
        <ActivityFeed projectId={params.id} />
      </div>

      <GenerationQueue projectId={params.id} />
      <NextStepButton projectId={params.id} current="generate" />
    </div>
  );
}
