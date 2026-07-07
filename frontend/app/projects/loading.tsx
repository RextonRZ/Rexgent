import { Skeleton } from "@/components/shared/Skeleton";
import { CardGridSkeleton } from "@/components/shared/PageSkeleton";

export default function ProjectsLoading() {
  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-3">
        <div className="space-y-2.5">
          <Skeleton className="h-8 w-52" />
          <Skeleton className="h-3.5 w-72 max-w-full" />
        </div>
        <Skeleton className="h-10 w-36 rounded-lg" />
      </div>
      {/* the drama poster wall */}
      <CardGridSkeleton
        count={8}
        cardClassName="h-72"
        cols="sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
      />
    </div>
  );
}
