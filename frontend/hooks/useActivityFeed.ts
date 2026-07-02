import { useEffect, useState } from "react";
import { getSocket } from "@/lib/websocket";

const EVENTS = [
  "casting.started",
  "casting.wardrobe_plan.completed",
  "casting.plate.started",
  "casting.plate.completed",
  "casting.awaiting_review",
  "casting.completed",
  "job:blocked",
  "job:budget_exhausted",
  "job:completed",
  "generation.shot.started",
  "generation.shot.completed",
  "continuity.scoring.started",
  "continuity.scoring.completed",
  "continuity.flagged",
  "cost:updated",
] as const;

export interface FeedItem {
  event: string;
  payload: any;
  at: number;
}

export function useActivityFeed(projectId: string) {
  const [items, setItems] = useState<FeedItem[]>([]);

  useEffect(() => {
    const socket = getSocket();
    socket.connect();
    socket.emit("join_project", { project_id: projectId });

    const handlers = EVENTS.map((event) => {
      const handler = (payload: any) =>
        setItems((prev) => [...prev, { event, payload, at: Date.now() }]);
      socket.on(event, handler);
      return [event, handler] as const;
    });

    return () => {
      handlers.forEach(([event, handler]) => socket.off(event, handler));
      socket.disconnect();
    };
  }, [projectId]);

  return items;
}
