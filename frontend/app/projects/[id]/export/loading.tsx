import { Skeleton } from "@/components/shared/Skeleton";
import {
  CardSkeleton,
  PageHeaderSkeleton,
} from "@/components/shared/PageSkeleton";

export default function ExportLoading() {
  return (
    <div className="space-y-6">
      <PageHeaderSkeleton />
      {/* phone-frame preview beside the cut controls */}
      <div className="grid gap-6 lg:grid-cols-3">
        <Skeleton className="mx-auto h-[420px] w-full max-w-[240px] rounded-3xl" />
        <div className="space-y-4 lg:col-span-2">
          <CardSkeleton className="h-40" />
          <CardSkeleton className="h-24" />
        </div>
      </div>
      {/* the timeline strip */}
      <div className="flex gap-2 overflow-hidden rounded-xl border hairline bg-card p-3">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-14 shrink-0 rounded-lg" />
        ))}
      </div>
    </div>
  );
}
