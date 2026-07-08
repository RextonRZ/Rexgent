"use client";

import { useEffect, useRef, useState } from "react";
import { GripVertical, PanelRightClose } from "lucide-react";
import { cn } from "@/lib/utils";
import { useLedger } from "@/hooks/useLedger";
import { useRunningStages } from "@/hooks/useLiveRun";
import { useReducedMotion } from "@/hooks/useReducedMotion";
import { CostPanelContent } from "@/components/budget/CostPanelContent";
import { AgentChat } from "@/components/agents/AgentChat";
import { CrewDockPanel, CrewModal } from "@/components/agents/CrewModal";

type PanelKey = "agent" | "cost" | "crew";
type OpenState = Record<PanelKey, boolean>;
type FloatPos = { x: number; y: number };

const PANEL_TITLES: Record<PanelKey, string> = {
  agent: "Showrunner",
  cost: "Live cost",
  crew: "Your crew",
};

const WINDOW_W = 320;
/** pointer inside this many px of the right edge = the dock wants it back */
const DOCK_ZONE = 200;

function PanelSection({
  title,
  onClose,
  onGripDown,
  children,
  grow = false,
  scroll = false,
  className,
}: {
  title: string;
  onClose: () => void;
  /** drag the panel out of the dock by its grip */
  onGripDown?: (e: React.PointerEvent) => void;
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
      <div className="flex items-center justify-between pl-2 pr-3 py-2.5 border-b hairline shrink-0">
        <span className="flex min-w-0 items-center gap-1">
          {onGripDown && (
            <button
              onPointerDown={onGripDown}
              aria-label={`Drag ${title} out of the dock`}
              title="Drag out to float this panel"
              className="cursor-grab touch-none rounded p-0.5 text-zinc-600 hover:text-zinc-300 active:cursor-grabbing"
            >
              <GripVertical className="size-3.5" />
            </button>
          )}
          <span className="truncate text-xs font-semibold">{title}</span>
        </span>
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

/** Right-edge dock hosting Showrunner chat + Live cost + Crew. The rail is a
 * thin icon strip; open panels stack in a column the layout flows around.
 * Any panel can be DRAGGED OUT by its grip into a floating window — and when
 * dragged back near the dock, it magnetically snaps home. */
export function DockRail({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState<OpenState>({
    agent: false,
    cost: false,
    crew: false,
  });
  const [crewOpen, setCrewOpen] = useState(false);
  const [floating, setFloating] = useState<Partial<Record<PanelKey, FloatPos>>>({});
  const [dragKey, setDragKey] = useState<PanelKey | null>(null);
  const [inDockZone, setInDockZone] = useState(false);
  const [returning, setReturning] = useState<PanelKey | null>(null);
  const dragOffset = useRef({ dx: 0, dy: 0 });
  const reduced = useReducedMotion();
  const ledger = useLedger(projectId);
  const grand = ledger?.grand_total ?? 0;
  // same live-run store the chat + crew panel + modal read — one source
  const running = useRunningStages(projectId);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("rx.dock.open");
      if (raw === null) {
        // first visit: the live agent activity + cost + crew panels ARE the
        // pitch — open by default so nobody has to discover the rail
        setOpen({ agent: true, cost: true, crew: true });
        return;
      }
      const saved = JSON.parse(raw);
      // crew was added later: saves without the key default to open
      setOpen({
        agent: !!saved.agent,
        cost: !!saved.cost,
        crew: saved.crew !== false,
      });
    } catch {
      /* older string format or bad value — start closed */
    }
  }, []);

  const toggle = (which: PanelKey) =>
    setOpen((cur) => {
      const next = { ...cur, [which]: !cur[which] };
      localStorage.setItem("rx.dock.open", JSON.stringify(next));
      // closing a panel also dismisses its floating window
      if (!next[which])
        setFloating((f) => {
          const n = { ...f };
          delete n[which];
          return n;
        });
      return next;
    });

  /** fly the window home, then re-dock it */
  const snapBack = (key: PanelKey) => {
    const finish = () =>
      setFloating((f) => {
        const n = { ...f };
        delete n[key];
        return n;
      });
    if (reduced) {
      finish();
      return;
    }
    setReturning(key);
    setFloating((f) => ({
      ...f,
      [key]: { x: window.innerWidth - WINDOW_W - 56, y: 64 },
    }));
    window.setTimeout(() => {
      finish();
      setReturning(null);
    }, 240);
  };

  const startDrag = (key: PanelKey) => (e: React.PointerEvent) => {
    e.preventDefault();
    const pos = floating[key];
    if (pos) {
      dragOffset.current = { dx: e.clientX - pos.x, dy: e.clientY - pos.y };
    } else {
      // tearing out of the dock: hold the window by its header
      dragOffset.current = { dx: WINDOW_W / 2, dy: 14 };
      setFloating((f) => ({
        ...f,
        [key]: { x: e.clientX - WINDOW_W / 2, y: e.clientY - 14 },
      }));
    }
    setDragKey(key);
  };

  useEffect(() => {
    if (!dragKey) return;
    const move = (e: PointerEvent) => {
      const x = Math.min(
        Math.max(e.clientX - dragOffset.current.dx, 8),
        window.innerWidth - 120
      );
      const y = Math.min(
        Math.max(e.clientY - dragOffset.current.dy, 8),
        window.innerHeight - 80
      );
      setFloating((f) => ({ ...f, [dragKey]: { x, y } }));
      setInDockZone(e.clientX > window.innerWidth - DOCK_ZONE);
    };
    const up = (e: PointerEvent) => {
      const key = dragKey;
      setDragKey(null);
      setInDockZone(false);
      if (key && e.clientX > window.innerWidth - DOCK_ZONE) snapBack(key);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dragKey]);

  const panelContent = (key: PanelKey) =>
    key === "agent" ? (
      <AgentChat projectId={projectId} />
    ) : key === "cost" ? (
      <CostPanelContent projectId={projectId} />
    ) : (
      <CrewDockPanel projectId={projectId} onOpenFull={() => setCrewOpen(true)} />
    );

  const docked = (key: PanelKey) => open[key] && !floating[key];
  const anyDocked = docked("agent") || docked("cost") || docked("crew");
  const floatingKeys = (Object.keys(floating) as PanelKey[]).filter(
    (k) => floating[k]
  );

  return (
    <aside className="hidden md:flex sticky top-14 h-[calc(100vh-3.5rem)] shrink-0 items-stretch">
      {anyDocked && (
        // one flex column, no outer scroll: the chat owns the only always-on
        // scrollbar and expands to the full height when cost is hidden
        <div
          className={cn(
            "flex w-80 min-h-0 flex-col divide-y divide-border overflow-hidden border-l hairline bg-card transition-shadow duration-150",
            dragKey && inDockZone && "ring-2 ring-inset ring-primary/50"
          )}
        >
          {docked("agent") && (
            <PanelSection
              title="Showrunner"
              grow
              onClose={() => toggle("agent")}
              onGripDown={startDrag("agent")}
            >
              <AgentChat projectId={projectId} />
            </PanelSection>
          )}
          {docked("cost") && (
            <PanelSection
              title="Live cost"
              onClose={() => toggle("cost")}
              onGripDown={startDrag("cost")}
              grow={!docked("agent")}
              scroll
              className={
                docked("agent")
                  ? docked("crew")
                    ? "max-h-[28%]"
                    : "max-h-[44%]"
                  : undefined
              }
            >
              <CostPanelContent projectId={projectId} />
            </PanelSection>
          )}

          {/* the crew runs across ALL five steps — a compact global pipeline */}
          {docked("crew") && (
            <PanelSection
              title="Your crew"
              onClose={() => toggle("crew")}
              onGripDown={startDrag("crew")}
              grow={!docked("agent") && !docked("cost")}
              scroll
            >
              <CrewDockPanel
                projectId={projectId}
                onOpenFull={() => setCrewOpen(true)}
              />
            </PanelSection>
          )}
        </div>
      )}

      <div
        className={cn(
          "w-12 border-l hairline bg-card/60 flex flex-col items-center gap-1 py-3 transition-shadow duration-150",
          dragKey && inDockZone && !anyDocked && "ring-2 ring-inset ring-primary/50"
        )}
      >
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
        <button
          onClick={() => toggle("crew")}
          title="Your crew"
          className={cn(
            "relative h-9 w-9 rounded-lg flex items-center justify-center text-sm transition-colors",
            open.crew
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground hover:bg-secondary"
          )}
        >
          🎬
          {running.length > 0 && (
            <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-violet-400 motion-safe:animate-pulse" />
          )}
        </button>
      </div>

      {/* ── torn-out panels: floating windows; drag near the dock to snap home ── */}
      {floatingKeys.map((key) => {
        const pos = floating[key]!;
        const isReturning = returning === key;
        const isDragging = dragKey === key;
        return (
          <div
            key={key}
            role="dialog"
            aria-label={`${PANEL_TITLES[key]} window`}
            className={cn(
              "fixed z-50 flex max-h-[70vh] flex-col overflow-hidden rounded-xl border border-white/10 bg-card shadow-2xl",
              isReturning &&
                "scale-90 opacity-60 transition-[left,top,transform,opacity] duration-200 ease-in",
              isDragging && "select-none",
              isDragging && inDockZone && "ring-2 ring-primary/60"
            )}
            style={{ left: pos.x, top: pos.y, width: WINDOW_W }}
          >
            <div
              onPointerDown={startDrag(key)}
              className="flex shrink-0 cursor-grab touch-none items-center justify-between border-b hairline bg-white/[0.02] py-2 pl-2 pr-2 active:cursor-grabbing"
            >
              <span className="flex items-center gap-1">
                <GripVertical className="size-3.5 text-zinc-600" />
                <span className="text-xs font-semibold">{PANEL_TITLES[key]}</span>
              </span>
              <span className="flex items-center gap-0.5">
                <button
                  onClick={() => snapBack(key)}
                  onPointerDown={(e) => e.stopPropagation()}
                  aria-label={`Return ${PANEL_TITLES[key]} to the dock`}
                  title="Return to dock"
                  className="flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground"
                >
                  <PanelRightClose className="size-3.5" />
                </button>
                <button
                  onClick={() => toggle(key)}
                  onPointerDown={(e) => e.stopPropagation()}
                  aria-label={`Close ${PANEL_TITLES[key]}`}
                  className="h-6 w-6 rounded-md text-xs text-muted-foreground hover:bg-secondary hover:text-foreground"
                >
                  ✕
                </button>
              </span>
            </div>
            <div className="scroll-clean min-h-0 flex-1 overflow-y-auto px-4 pb-4 pt-3">
              {panelContent(key)}
            </div>
          </div>
        );
      })}

      <CrewModal
        projectId={projectId}
        open={crewOpen}
        onOpenChange={setCrewOpen}
        // keep the dock clear: rail (48px) + panel column (320px) when open
        insetRight={anyDocked ? 368 : 48}
      />
    </aside>
  );
}
