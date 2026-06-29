"use client";

import { ClipProgressCard } from "./ClipProgressCard";
import { useGenerationStore } from "@/stores/generationStore";

export function GenerationQueue() {
  const clips = useGenerationStore((s) => s.clips);
  const list = Object.values(clips);

  if (list.length === 0) {
    return (
      <p className="text-center text-muted-foreground py-8">
        No clips yet. Start generation to watch progress live.
      </p>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {list.map((clip) => (
        <ClipProgressCard key={clip.shot_id} clip={clip} />
      ))}
    </div>
  );
}
