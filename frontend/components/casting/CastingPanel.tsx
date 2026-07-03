"use client";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/shared/Skeleton";
import { ActivityFeed } from "./ActivityFeed";
import {
  useBible,
  useApproveCasting,
  useSetAutoApprove,
} from "@/hooks/useCasting";

/** The spend gate on the Generate step: readiness summary + approve casting.
 *  Plates are reviewed upstream (Characters + Storyboard steps). */
export function CastingPanel({ projectId }: { projectId: string }) {
  const { data: bible, isLoading } = useBible(projectId);
  const approveCasting = useApproveCasting(projectId);
  const setAutoApprove = useSetAutoApprove(projectId);

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24 rounded-xl" />
      </div>
    );
  }

  if (!bible) {
    return (
      <div className="rounded-xl border hairline bg-card p-8 text-center text-sm text-muted-foreground">
        No casting data yet. Run the storyboard step first, then generate plates
        on the Characters step.
      </div>
    );
  }

  const charactersReady = bible.characters.filter(
    (c) => c.variants.length > 0
  ).length;

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2 space-y-3">
        <div className="glass rounded-xl p-4 flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h2 className="font-semibold">Casting review</h2>
            <p className="text-sm text-muted-foreground max-w-md">
              Character plates live on the{" "}
              <span className="text-primary">Characters</span> step; locations
              &amp; style on the{" "}
              <span className="text-primary">Storyboard</span> step. Approve
              here before spend continues.
            </p>
            <p className="text-[11px] text-muted-foreground mt-1">
              {charactersReady}/{bible.characters.length} characters have plates
              · {bible.locations.length} locations ·{" "}
              {bible.style ? "style set" : "no style"}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
              <input
                type="checkbox"
                checked={bible.auto_approve_casting}
                onChange={(e) => setAutoApprove.mutate(e.target.checked)}
                disabled={setAutoApprove.isPending}
                className="h-4 w-4 rounded border-border accent-primary"
              />
              Auto-approve casting
            </label>
            {!bible.auto_approve_casting && (
              <Button
                onClick={() => approveCasting.mutate()}
                disabled={approveCasting.isPending}
              >
                {approveCasting.isPending
                  ? "Approving…"
                  : "✓ Approve casting → Generate"}
              </Button>
            )}
          </div>
        </div>

        {approveCasting.isError && (
          <p className="text-sm text-bad">
            {(approveCasting.error as Error).message}
          </p>
        )}
      </div>

      <div>
        <ActivityFeed projectId={projectId} />
      </div>
    </div>
  );
}
