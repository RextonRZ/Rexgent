import type { ClipProgress } from "@/stores/generationStore";

export function clipStatusChip(status: ClipProgress["status"]) {
  switch (status) {
    case "APPROVED":
      return { label: "verified", cls: "bg-ok/20 text-ok" };
    case "NEEDS_REVIEW":
      return { label: "needs review", cls: "bg-warn/20 text-warn" };
    case "FAILED":
      return { label: "failed", cls: "bg-bad/20 text-bad" };
    default:
      return { label: status.toLowerCase(), cls: "bg-secondary text-muted-foreground" };
  }
}
