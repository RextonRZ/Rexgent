"use client";

import { useWebSocket } from "@/hooks/useWebSocket";
import { GenerationLauncher } from "@/components/generate/GenerationLauncher";
import { GenerationQueue } from "@/components/generate/GenerationQueue";
import { CostTracker } from "@/components/generate/CostTracker";

export default function GeneratePage({ params }: { params: { id: string } }) {
  useWebSocket(params.id);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Video Generation</h1>
      <CostTracker />
      <GenerationLauncher projectId={params.id} />
      <GenerationQueue />
    </div>
  );
}
