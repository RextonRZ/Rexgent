import { cn } from "@/lib/utils";
import type { ClipProgress } from "@/stores/generationStore";

const MAP: Record<string, { label: string; cls: string; dot: string }> = {
  PENDING: { label: "Queued", cls: "bg-secondary text-muted-foreground", dot: "bg-muted-foreground" },
  GENERATING: { label: "Generating", cls: "bg-hh/15 text-hh", dot: "bg-hh animate-pulse" },
  CHECKING: { label: "Self-correcting", cls: "bg-warn/15 text-warn", dot: "bg-warn animate-pulse" },
  APPROVED: { label: "Verified", cls: "bg-ok/15 text-ok", dot: "bg-ok" },
  NEEDS_REVIEW: { label: "Needs review", cls: "bg-warn/15 text-warn", dot: "bg-warn" },
  FAILED: { label: "Failed", cls: "bg-bad/15 text-bad", dot: "bg-bad" },
};

export function ConsistencyBadge({ status }: { status: ClipProgress["status"] }) {
  const m = MAP[status] || MAP.PENDING;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium",
        m.cls
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", m.dot)} />
      {m.label}
    </span>
  );
}
