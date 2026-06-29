"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Timeline } from "@/components/edit/Timeline";
import { ClipViewer } from "@/components/edit/ClipViewer";
import { FlagPanel } from "@/components/edit/FlagPanel";
import { useEditStore } from "@/stores/editStore";

export default function EditPage({ params }: { params: { id: string } }) {
  const selectedClip = useEditStore((s) => s.selectedClip);
  const queryClient = useQueryClient();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Edit</h1>
        <p className="text-sm text-muted-foreground">
          Review every clip; flag and regenerate anything that disappoints.
        </p>
      </div>

      <div className="glass rounded-xl p-3">
        <Timeline projectId={params.id} />
      </div>

      {selectedClip ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <ClipViewer clip={selectedClip} />
          <FlagPanel
            clipId={selectedClip.id}
            originalUrl={selectedClip.url}
            onApproved={() =>
              queryClient.invalidateQueries({ queryKey: ["clips", params.id] })
            }
          />
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Select a clip from the timeline to review or regenerate it.
        </p>
      )}
    </div>
  );
}
