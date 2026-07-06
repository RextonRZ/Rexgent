"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { useLedger } from "@/hooks/useLedger";
import { CostPanelContent } from "@/components/budget/CostPanelContent";
import { AgentChat } from "@/components/agents/AgentChat";

type PanelKey = "agent" | "cost";
type OpenState = Record<PanelKey, boolean>;

function PanelSection({
  title,
  onClose,
  children,
  grow = false,
  scroll = false,
  className,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  /** take all remaining column height (the child manages its own scroll) */
  grow?: boolean;
  /** the section body scrolls itself (for fixed-height sections) */
  scroll?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex min-h-0 flex-col overflow-x-hidden",
        grow ? "flex-1" : "shrink-0",
        className
      )}
    >
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
      <div
        className={cn(
          "min-h-0 flex-1 overflow-x-hidden px-4 pt-3",
          scroll ? "scroll-clean overflow-y-auto pb-5" : "pb-3"
        )}
      >
        {children}
      </div>
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
        // one flex column, no outer scroll: the chat owns the only always-on
        // scrollbar and expands to the full height when cost is hidden
        <div className="flex w-80 min-h-0 flex-col divide-y divide-border overflow-hidden border-l hairline bg-card">
          {open.agent && (
            <PanelSection title="Showrunner" grow onClose={() => toggle("agent")}>
              <AgentChat projectId={projectId} />
            </PanelSection>
          )}
          {open.cost && (
            <PanelSection
              title="Live cost"
              onClose={() => toggle("cost")}
              grow={!open.agent}
              scroll
              className={open.agent ? "max-h-[44%]" : undefined}
            >
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
