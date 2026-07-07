import { Skeleton } from "@/components/shared/Skeleton";
import {
  PageHeaderSkeleton,
  RowsSkeleton,
  StripSkeleton,
} from "@/components/shared/PageSkeleton";

export default function StoryboardLoading() {
  return (
    <div className="space-y-6">
      <PageHeaderSkeleton actions={1} />
      <StripSkeleton />
      {/* tabs bar */}
      <Skeleton className="h-9 w-44 rounded-lg" />
      {/* shots (wide) beside the scene rail */}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <RowsSkeleton rows={6} />
          <RowsSkeleton rows={4} />
        </div>
        <RowsSkeleton rows={7} />
      </div>
    </div>
  );
}
