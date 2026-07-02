"use client";

import { Button } from "@/components/ui/button";
import { PlateCard } from "./PlateCard";
import { ActivityFeed } from "./ActivityFeed";
import {
  useBible,
  useApproveCasting,
  useRegenerateVariant,
  useSetAutoApprove,
  useRunCasting,
  useOverrideVariant,
} from "@/hooks/useCasting";

export function CastingPanel({ projectId }: { projectId: string }) {
  const { data: bible, isLoading } = useBible(projectId);
  const approveCasting = useApproveCasting(projectId);
  const regenerateVariant = useRegenerateVariant();
  const setAutoApprove = useSetAutoApprove(projectId);
  const runCasting = useRunCasting(projectId);
  const overrideVariant = useOverrideVariant();

  if (isLoading) {
    return (
      <div className="rounded-xl border hairline bg-card p-8 text-center text-sm text-muted-foreground">
        Loading casting…
      </div>
    );
  }

  if (!bible) {
    return (
      <div className="rounded-xl border hairline bg-card p-8 text-center text-sm text-muted-foreground">
        No casting data yet. Run the storyboard step first, then casting will
        generate character, location, and style plates here.
      </div>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2 space-y-6">
        {/* top bar */}
        <div className="glass rounded-xl p-4 flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h2 className="font-semibold">Casting review</h2>
            <p className="text-sm text-muted-foreground max-w-md">
              Review every character costume, location, and style plate before
              spend continues.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex flex-col items-end gap-1">
              <Button
                variant="outline"
                onClick={() => runCasting.mutate()}
                disabled={runCasting.isPending}
              >
                {runCasting.isPending ? "Generating…" : "Generate plates"}
              </Button>
              <p className="text-[11px] text-muted-foreground">
                Generates character, location & style plates
              </p>
            </div>
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
                className="glow"
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

        {/* characters */}
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-primary/80">Characters</h3>
          {bible.characters.length === 0 ? (
            <p className="text-xs text-muted-foreground">No characters yet.</p>
          ) : (
            bible.characters.map((character) => (
              <div key={character.id} className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground">
                  {character.name}
                </p>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {character.variants.map((variant) => (
                    <PlateCard
                      key={variant.id}
                      imageUrl={variant.plate_image_url ?? undefined}
                      label={
                        variant.label +
                        (variant.is_default ? " (default)" : "")
                      }
                      description={variant.outfit_description ?? undefined}
                      status={variant.plate_status}
                      onRegenerate={() =>
                        regenerateVariant.mutate(variant.id)
                      }
                      onUpload={(file) =>
                        overrideVariant.mutate({ variantId: variant.id, file })
                      }
                    />
                  ))}
                </div>
              </div>
            ))
          )}
        </section>

        {/* locations */}
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-primary/80">Locations</h3>
          {bible.locations.length === 0 ? (
            <p className="text-xs text-muted-foreground">No locations yet.</p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {bible.locations.map((location) => (
                <PlateCard
                  key={location.id}
                  imageUrl={location.plate_image_url ?? undefined}
                  label={location.location_key}
                  description={location.description ?? undefined}
                />
              ))}
            </div>
          )}
        </section>

        {/* style */}
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-primary/80">Style</h3>
          {bible.style ? (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <PlateCard
                imageUrl={bible.style.plate_image_url ?? undefined}
                label="Style preset"
                description={bible.style.style_tags.join(", ")}
              />
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              No style preset yet.
            </p>
          )}
        </section>
      </div>

      {/* activity feed */}
      <div>
        <ActivityFeed projectId={projectId} />
      </div>
    </div>
  );
}
