"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { FlagPanel } from "@/components/edit/FlagPanel";
import type { GeneratedClip } from "@/lib/types";

/** A pop-up that shows a take larger with the AI-edit (flag & regenerate) panel. */
export function ClipEditModal({
  clip,
  projectId,
  label,
  onClose,
}: {
  clip: GeneratedClip | null;
  projectId: string;
  label?: string;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const queryClient = useQueryClient();
  if (!clip) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-xl border hairline bg-card p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">
            AI edit{label ? ` — ${label}` : ""}
          </h2>
          <button
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-white/5 hover:text-foreground"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <video
            src={clip.url ?? undefined}
            controls
            autoPlay
            loop
            playsInline
            className="w-full rounded-lg bg-black aspect-video object-contain"
          />
          <FlagPanel
            clipId={clip.id}
            originalUrl={clip.url}
            onApproved={() => {
              queryClient.invalidateQueries({ queryKey: ["clips", projectId] });
              onClose();
            }}
          />
        </div>
      </div>
    </div>
  );
}
