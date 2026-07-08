import { Skeleton } from "@/components/shared/Skeleton";

/** Mirrors the dashboard's exact frame: glass header, the recap shelf's
 * two-column hero (copy left, film screen right), the toolbar, then the
 * poster grid — so the swap to live content doesn't jump. */
export default function ProjectsLoading() {
  return (
    <main className="min-h-screen">
      {/* sticky glass header: wordmark left, avatar right */}
      <div className="sticky top-0 z-40 border-b hairline">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-6">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-8 w-8 rounded-full" />
        </div>
      </div>

      <div className="mx-auto max-w-7xl space-y-10 px-6 py-8">
        {/* recap shelf: copy + stats (2fr) beside the film-frame screen (3fr) */}
        <div className="grid items-center gap-10 lg:grid-cols-[2fr_3fr]">
          <div className="space-y-4">
            <Skeleton className="h-9 w-4/5" />
            <Skeleton className="h-4 w-3/5" />
            <div className="flex gap-6 pt-2">
              <Skeleton className="h-3.5 w-20" />
              <Skeleton className="h-3.5 w-24" />
              <Skeleton className="h-3.5 w-16" />
            </div>
            <Skeleton className="h-10 w-40 rounded-lg" />
          </div>
          <div className="flex items-stretch overflow-hidden rounded-2xl border hairline bg-card">
            {/* sprocket strips frame the screen, like the real shelf */}
            <div className="flex w-6 shrink-0 flex-col items-center justify-center gap-4 py-3">
              {Array.from({ length: 7 }).map((_, i) => (
                <Skeleton key={i} className="h-[9px] w-[7px] rounded-[2px]" />
              ))}
            </div>
            <Skeleton className="my-2 aspect-video min-w-0 flex-1 rounded-[3px]" />
            <div className="flex w-6 shrink-0 flex-col items-center justify-center gap-4 py-3">
              {Array.from({ length: 7 }).map((_, i) => (
                <Skeleton key={i} className="h-[9px] w-[7px] rounded-[2px]" />
              ))}
            </div>
          </div>
        </div>

        {/* toolbar: title + count, search + filters right */}
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-5 w-8 rounded-full" />
            <div className="ml-auto flex items-center gap-2">
              <Skeleton className="h-9 w-56 rounded-lg" />
              <Skeleton className="h-9 w-24 rounded-lg" />
            </div>
          </div>

          {/* the drama poster wall: 16:10 cards + title/meta lines */}
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="space-y-2">
                <Skeleton className="aspect-[16/10] w-full rounded-xl" />
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-3 w-2/5" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
