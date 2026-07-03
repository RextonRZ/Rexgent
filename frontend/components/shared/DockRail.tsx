"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { useLedger } from "@/hooks/useLedger";
import { CostPanelContent } from "@/components/budget/CostPanelContent";
import { AgentPanelContent } from "@/components/agents/AgentPanelContent";

type PanelKey = "agent" | "cost";

/** Right-edge dock hosting Live cost + Agent activity. The rail is always a thin
 *  icon strip; opening a panel expands a column that the page layout flows around
 *  — it never overlaps the main content. */
export function DockRail({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState<PanelKey | null>(null);
  const ledger = useLedger(projectId);
  const grand = ledger?.grand_total ?? 0;

  useEffect(() => {
    const saved = localStorage.getItem("rx.dock.open");
    if (saved === "cost" || saved === "agent") setOpen(saved);
  }, []);

  const toggle = (which: PanelKey) =>
    setOpen((cur) => {
      const next = cur === which ? null : which;
      localStorage.setItem("rx.dock.open", next ?? "");
      return next;
    });

  return (
    <aside className="hidden md:flex sticky top-14 h-[calc(100vh-3.5rem)] shrink-0 items-stretch">
      {open && (
        <div className="w-80 border-l hairline bg-card flex flex-col">
          <div className="flex items-center justify-between px-3 py-2 border-b hairline shrink-0">
            <span className="text-xs font-semibold">
              {open === "cost" ? "Live cost" : "Agent activity"}
            </span>
            <button
              onClick={() => toggle(open)}
              aria-label="Close panel"
              className="h-6 w-6 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary text-xs"
            >
              ✕
            </button>
          </div>
          <div className="overflow-y-auto p-3">
            {open === "cost" ? (
              <CostPanelContent projectId={projectId} />
            ) : (
              <AgentPanelContent projectId={projectId} />
            )}
          </div>
        </div>
      )}

      <div className="w-12 border-l hairline bg-card/60 flex flex-col items-center gap-1 py-3">
        <button
          onClick={() => toggle("agent")}
          title="Agent activity"
          className={cn(
            "h-9 w-9 rounded-lg flex items-center justify-center text-sm transition-colors",
            open === "agent"
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground hover:bg-secondary"
          )}
        >
          ⚡
        </button>
        <button
          onClick={() => toggle("cost")}
          title="Live cost"
          className={cn(
            "h-11 w-9 rounded-lg flex flex-col items-center justify-center transition-colors",
            open === "cost"
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground hover:bg-secondary"
          )}
        >
          <span className="text-sm leading-none">$</span>
          <span className="text-[9px] leading-tight tabular-nums">
            {grand.toFixed(grand >= 10 ? 0 : 1)}
          </span>
        </button>
      </div>
    </aside>
  );
}
