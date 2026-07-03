import { cn } from "@/lib/utils";

/** Neutral shimmer block for loading states. Compose to mimic real content. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn("animate-pulse rounded-md bg-secondary/60", className)} />
  );
}
