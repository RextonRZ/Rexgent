"use client";

import { useWebSocket } from "@/hooks/useWebSocket";
import { GenerationLauncher } from "@/components/generate/GenerationLauncher";
import { GenerationQueue } from "@/components/generate/GenerationQueue";
import { CostTracker } from "@/components/generate/CostTracker";
import { CastingPanel } from "@/components/casting/CastingPanel";
import { CostLedger } from "@/components/budget/CostLedger";
import { AgentDecisionPanel } from "@/components/agents/AgentDecisionPanel";
import { ClarificationModal } from "@/components/agents/ClarificationModal";

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

      <div>
        <h2 className="text-lg font-semibold tracking-tight mb-3">Casting</h2>
        <CastingPanel projectId={params.id} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <GenerationLauncher projectId={params.id} />
        </div>
        <div className="space-y-6">
          <CostTracker />
          <CostLedger projectId={params.id} />
          <AgentDecisionPanel projectId={params.id} />
        </div>
      </div>

      <GenerationQueue />
    </div>
  );
}
