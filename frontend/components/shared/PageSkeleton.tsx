import { Skeleton } from "@/components/shared/Skeleton";

/** ── instant route skeletons ─────────────────────────────────────────────
 * Every pipeline page ships a loading.tsx composed from these, so clicking
 * Script → Characters → Storyboard paints a page-shaped placeholder the very
 * frame the route changes — no frozen previous page, no blank flash. Shapes
 * mirror each page's real layout (masthead, strips, card grids) so the swap
 * to live content doesn't jump.
 */

/** Masthead placeholder matching PageHeader's rounded card. */
export function PageHeaderSkeleton({ actions = 0 }: { actions?: number }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 rounded-2xl border hairline bg-card px-5 py-4">
      <div className="space-y-2.5">
        <Skeleton className="h-7 w-44" />
        <Skeleton className="h-3.5 w-72 max-w-full" />
      </div>
      {actions > 0 && (
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: actions }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-32 rounded-lg" />
          ))}
        </div>
      )}
    </div>
  );
}

/** The thin live-status strip under mastheads. */
export function StripSkeleton() {
  return <Skeleton className="h-10 w-full rounded-xl" />;
}

/** A generic content card. */
export function CardSkeleton({ className = "h-40" }: { className?: string }) {
  return <Skeleton className={`w-full rounded-xl ${className}`} />;
}

/** Grid of cards (character cast, clip queue, poster wall …). */
export function CardGridSkeleton({
  count = 6,
  cardClassName = "h-56",
  cols = "sm:grid-cols-2 lg:grid-cols-3",
}: {
  count?: number;
  cardClassName?: string;
  cols?: string;
}) {
  return (
    <div className={`grid gap-4 ${cols}`}>
      {Array.from({ length: count }).map((_, i) => (
        <CardSkeleton key={i} className={cardClassName} />
      ))}
    </div>
  );
}

/** Stacked text rows (beat sheets, shot lists, activity feeds). */
export function RowsSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2 rounded-xl border hairline bg-card p-4">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Skeleton className="h-8 w-8 shrink-0 rounded-full" />
          <div className="min-w-0 flex-1 space-y-1.5">
            <Skeleton className="h-3 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}
