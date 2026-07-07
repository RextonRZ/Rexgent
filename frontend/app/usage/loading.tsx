import { Skeleton } from "@/components/shared/Skeleton";
import {
  CardGridSkeleton,
  CardSkeleton,
  PageHeaderSkeleton,
} from "@/components/shared/PageSkeleton";

export default function UsageLoading() {
  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-5xl space-y-10 px-6 py-8">
        <PageHeaderSkeleton actions={1} />
        {/* hero routing card */}
        <CardSkeleton className="h-48" />
        {/* roster grid */}
        <CardGridSkeleton count={4} cardClassName="h-52" cols="lg:grid-cols-2" />
        {/* money row */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
        <CardSkeleton className="h-64" />
      </div>
    </main>
  );
}
