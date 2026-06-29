"use client";

import { TimelineClip } from "./TimelineClip";
import { useLatestJobClips } from "@/hooks/useClips";
import { useEditStore } from "@/stores/editStore";

export function Timeline({ projectId }: { projectId: string }) {
  const { data, isLoading, isError } = useLatestJobClips(projectId);
  const { selectedClip, setSelectedClip } = useEditStore();

  if (isLoading) return <p className="text-muted-foreground">Loading clips...</p>;
  if (isError || !data?.clips?.length) {
    return (
      <p className="text-center text-muted-foreground py-8">
        No generated clips yet. Run generation first.
      </p>
    );
  }

  return (
    <div className="flex gap-2 overflow-x-auto pb-3">
      {data.clips.map((clip) => (
        <TimelineClip
          key={clip.id}
          clip={clip}
          selected={selectedClip?.id === clip.id}
          onClick={() => setSelectedClip(clip)}
        />
      ))}
    </div>
  );
}
