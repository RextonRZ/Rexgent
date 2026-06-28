import { LoadingSpinner } from "@/components/shared/LoadingSpinner";

export default function ScriptLoading() {
  return (
    <div className="flex items-center justify-center min-h-[50vh]">
      <LoadingSpinner size="lg" />
    </div>
  );
}
