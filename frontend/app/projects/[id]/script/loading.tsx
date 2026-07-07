import { Skeleton } from "@/components/shared/Skeleton";
import {
  CardSkeleton,
  PageHeaderSkeleton,
  RowsSkeleton,
} from "@/components/shared/PageSkeleton";

export default function ScriptLoading() {
  return (
    <div className="space-y-6">
      <PageHeaderSkeleton actions={2} />
      {/* tabs bar */}
      <Skeleton className="h-9 w-56 rounded-lg" />
      {/* the editor beside the beat sheet */}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <CardSkeleton className="h-[420px]" />
        </div>
        <RowsSkeleton rows={7} />
      </div>
    </div>
  );
}
