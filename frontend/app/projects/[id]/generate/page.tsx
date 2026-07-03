"use client";

import { useWebSocket } from "@/hooks/useWebSocket";
import { GenerationLauncher } from "@/components/generate/GenerationLauncher";
import { GenerationQueue } from "@/components/generate/GenerationQueue";
import { CastingPanel } from "@/components/casting/CastingPanel";
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

      <GenerationLauncher projectId={params.id} />
      <GenerationQueue projectId={params.id} />
    </div>
  );
}
