import { Badge } from "@/components/ui/badge";
import type { ClipProgress } from "@/stores/generationStore";

const MAP: Record<string, { label: string; cls: string }> = {
  PENDING: { label: "Queued", cls: "bg-slate-300" },
  GENERATING: { label: "Generating", cls: "bg-blue-500" },
  CHECKING: { label: "Retrying", cls: "bg-yellow-500" },
  APPROVED: { label: "✓ Passed", cls: "bg-green-500" },
  NEEDS_REVIEW: { label: "Needs review", cls: "bg-orange-500" },
  FAILED: { label: "✗ Failed", cls: "bg-red-500" },
};

export function ConsistencyBadge({ status }: { status: ClipProgress["status"] }) {
  const m = MAP[status] || MAP.PENDING;
  return <Badge className={m.cls}>{m.label}</Badge>;
}
