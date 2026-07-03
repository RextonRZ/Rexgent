"use client";

import { useBible } from "@/hooks/useCasting";
import { PlateCard } from "./PlateCard";
import { Skeleton } from "@/components/shared/Skeleton";

/** Review the world: location plates + the style preset for the project. */
export function LocationStylePanel({ projectId }: { projectId: string }) {
  const { data: bible, isLoading } = useBible(projectId);

  if (isLoading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-56 rounded-xl" />
        ))}
      </div>
    );
  }

  if (!bible) {
    return (
      <p className="text-sm text-muted-foreground py-8 text-center">
        No casting data yet — generate plates from the Characters step first.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <h3 className="text-xs uppercase tracking-wide text-muted-foreground">
          Locations
        </h3>
        {bible.locations.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No location plates yet — run Generate Plates on the Characters step.
          </p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {bible.locations.map((location) => (
              <PlateCard
                key={location.id}
                imageUrl={location.plate_image_url ?? undefined}
                // human-readable name, not the snake_case key
                label={
                  location.description ||
                  location.location_key.replace(/_/g, " ")
                }
              />
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h3 className="text-xs uppercase tracking-wide text-muted-foreground">
          Style
        </h3>
        {bible.style ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <PlateCard
              imageUrl={bible.style.plate_image_url ?? undefined}
              label="Style preset"
              description={bible.style.style_tags.join(", ")}
            />
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">No style preset yet.</p>
        )}
      </section>
    </div>
  );
}
