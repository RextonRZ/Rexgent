"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { getSocket } from "@/lib/websocket";
import type { StageProgress } from "@/hooks/useAgentChat";

/** Inline progress next to the button that started the work, so the user sees
 * life exactly where they clicked. Real backend events drive it; while none
 * have arrived yet (or the socket is down) a rotating fallback plus elapsed
 * time still proves the studio is working. */
export function LiveStageStrip({
  projectId,
  stage,
  pending,
  fallback,
  className,
}: {
  projectId: string;
  stage: string;
  pending: boolean;
  /** rotating copy shown until the first real event lands */
  fallback: string[];
  className?: string;
}) {
  const [live, setLive] = useState<StageProgress | null>(null);
  const [finished, setFinished] = useState<StageProgress | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const startedAt = useRef<number | null>(null);
  const [fallbackIdx, setFallbackIdx] = useState(0);

  useEffect(() => {
    const socket = getSocket();
    socket.connect();
    socket.emit("join_project", { project_id: projectId });
    const handler = (p: StageProgress) => {
      if (p?.stage !== stage) return;
      if (p.status === "completed" || p.status === "failed") {
        setLive(null);
        setFinished(p);
      } else {
        setFinished(null);
        setLive(p);
      }
    };
    socket.on("stage:progress", handler);
    return () => {
      socket.off("stage:progress", handler);
    };
  }, [projectId, stage]);

  // elapsed clock + fallback rotation while anything is in flight
  const active = pending || live !== null;
  useEffect(() => {
    if (!active) {
      startedAt.current = null;
      setFallbackIdx(0);
      return;
    }
    startedAt.current = startedAt.current ?? Date.now();
    const t = setInterval(() => {
      setNow(Date.now());
      setFallbackIdx((i) => i + 1);
    }, 1000);
    return () => clearInterval(t);
  }, [active]);

  // let the completion note linger briefly, then clear
  useEffect(() => {
    if (!finished) return;
    const t = setTimeout(() => setFinished(null), 6000);
    return () => clearTimeout(t);
  }, [finished]);

  if (!active && !finished) return null;

  if (!active && finished) {
    const ok = finished.status === "completed";
    return (
      <div
        className={cn(
          "flex items-center gap-2 rounded-lg border px-3 py-2 text-xs",
          ok ? "border-ok/20 bg-ok/[0.06] text-ok" : "border-bad/20 bg-bad/[0.06] text-bad",
          className
        )}
      >
        <span>{ok ? "✓" : "✕"}</span>
        <span className="text-foreground/90">{finished.label}</span>
      </div>
    );
  }

  const secs = startedAt.current
    ? Math.max(0, Math.floor((now - startedAt.current) / 1000))
    : 0;
  const label = live?.label ?? fallback[Math.floor(fallbackIdx / 4) % fallback.length];

  return (
    <div
      className={cn(
        "flex items-center gap-2.5 rounded-lg border border-primary/20 bg-primary/[0.06] px-3 py-2",
        className
      )}
    >
      <span className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs text-foreground/90">
          {live?.agent && <span className="font-medium">{live.agent}: </span>}
          {label}
          {live?.index && live?.total ? (
            <span className="ml-1 tabular-nums text-muted-foreground">
              {live.index}/{live.total}
            </span>
          ) : null}
        </p>
        {live?.total ? (
          <div className="mt-1 h-1 overflow-hidden rounded-full bg-secondary">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${((live.index ?? 0) / live.total) * 100}%` }}
            />
          </div>
        ) : null}
      </div>
      <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground">
        {secs >= 60 ? `${Math.floor(secs / 60)}m ${secs % 60}s` : `${secs}s`}
      </span>
    </div>
  );
}
