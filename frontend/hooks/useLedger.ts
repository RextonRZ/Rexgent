import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { getSocket } from "@/lib/websocket";

export interface Ledger {
  by_category: Record<string, number>;
  by_stage: Record<string, number>;
  grand_total: number;
  budget: number;
  within_budget: boolean;
  remaining: number;
}

export function useLedger(projectId: string) {
  const q = useQuery<Ledger>({
    queryKey: ["ledger", projectId],
    queryFn: async () =>
      (await api.get(`/api/budget/ledger/${projectId}`)).data,
    enabled: !!projectId,
  });

  const [live, setLive] = useState<Ledger | null>(null);

  useEffect(() => {
    const socket = getSocket();
    socket.connect();
    socket.emit("join_project", { project_id: projectId });

    const handler = (payload: Ledger) => setLive(payload);
    socket.on("cost:updated", handler);

    return () => {
      socket.off("cost:updated", handler);
      socket.disconnect();
    };
  }, [projectId]);

  return live ?? q.data ?? null;
}
