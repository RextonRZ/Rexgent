import {
  CardSkeleton,
  PageHeaderSkeleton,
  RowsSkeleton,
} from "@/components/shared/PageSkeleton";

export default function GenerateLoading() {
  return (
    <div className="space-y-6">
      <PageHeaderSkeleton />
      {/* token dashboard */}
      <CardSkeleton className="h-28" />
      {/* launcher beside the activity feed */}
      <div className="grid items-start gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <CardSkeleton className="h-72" />
        </div>
        <RowsSkeleton rows={6} />
      </div>
      {/* the clip queue */}
      <CardSkeleton className="h-40" />
    </div>
  );
}
