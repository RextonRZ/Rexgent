"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { useLedger } from "@/hooks/useLedger";
import { CostPanelContent } from "@/components/budget/CostPanelContent";
import { AgentPanelContent } from "@/components/agents/AgentPanelContent";

type PanelKey = "agent" | "cost";
type OpenState = Record<PanelKey, boolean>;

function PanelSection({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col min-h-0">
      <div className="flex items-center justify-between pl-4 pr-3 py-2.5 border-b hairline shrink-0">
        <span className="text-xs font-semibold">{title}</span>
        <button
          onClick={onClose}
          aria-label={`Close ${title}`}
          className="h-6 w-6 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary text-xs"
        >
          ✕
        </button>
      </div>
      {/* generous bottom padding so stacked panels don't butt against each other */}
      <div className="px-4 pt-3 pb-6 overflow-x-hidden">{children}</div>
    </div>
  );
}

/** Right-edge dock hosting Live cost + Agent activity. The rail is always a thin
 *  icon strip; open panels stack in a column the page layout flows around — they
 *  never overlap the main content, and both can be open at once. */
export function DockRail({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState<OpenState>({ agent: false, cost: false });
  const ledger = useLedger(projectId);
  const grand = ledger?.grand_total ?? 0;

  useEffect(() => {
    try {
      const raw = localStorage.getItem("rx.dock.open");
      if (raw === null) {
        // first visit: the live agent activity + cost panels ARE the pitch —
        // open by default so nobody has to discover the rail
        setOpen({ agent: true, cost: true });
        return;
      }
      const saved = JSON.parse(raw);
      setOpen({ agent: !!saved.agent, cost: !!saved.cost });
    } catch {
      /* older string format or bad value — start closed */
    }
  }, []);

  const toggle = (which: PanelKey) =>
    setOpen((cur) => {
      const next = { ...cur, [which]: !cur[which] };
      localStorage.setItem("rx.dock.open", JSON.stringify(next));
      return next;
    });

  const anyOpen = open.agent || open.cost;

  return (
    <aside className="hidden md:flex sticky top-14 h-[calc(100vh-3.5rem)] shrink-0 items-stretch">
      {anyOpen && (
        <div className="w-80 border-l hairline bg-card flex flex-col divide-y divide-border overflow-y-auto">
          {open.agent && (
            <PanelSection title="Agent activity" onClose={() => toggle("agent")}>
              <AgentPanelContent projectId={projectId} />
            </PanelSection>
          )}
          {open.cost && (
            <PanelSection title="Live cost" onClose={() => toggle("cost")}>
              <CostPanelContent projectId={projectId} />
            </PanelSection>
          )}
        </div>
      )}

      <div className="w-12 border-l hairline bg-card/60 flex flex-col items-center gap-1 py-3">
        <button
          onClick={() => toggle("agent")}
          title="Agent activity"
          className={cn(
            "h-9 w-9 rounded-lg flex items-center justify-center text-sm transition-colors",
            open.agent
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
            open.cost
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
