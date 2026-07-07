import {
  CardGridSkeleton,
  PageHeaderSkeleton,
  StripSkeleton,
} from "@/components/shared/PageSkeleton";

export default function CharactersLoading() {
  return (
    <div className="space-y-6">
      <PageHeaderSkeleton actions={3} />
      <StripSkeleton />
      {/* the cast grid */}
      <CardGridSkeleton count={6} cardClassName="h-64" />
    </div>
  );
}
