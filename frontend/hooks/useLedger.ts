import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { getSocket } from "@/lib/websocket";

export interface LedgerLlm {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  by_model: Record<string, { tokens: number; usd: number }>;
  tokens_by_stage: Record<string, number>;
}

export interface Ledger {
  by_category: Record<string, number>;
  /** per-model media detail: {video|image|tts: {model: {qty, usd}}} */
  media_models?: Record<string, Record<string, { qty: number; usd: number }>>;
  by_stage: Record<string, number>;
  grand_total: number;
  budget: number;
  within_budget: boolean;
  remaining: number;
  llm?: LedgerLlm;
}

export function useLedger(projectId: string) {
  const q = useQuery<Ledger>({
    queryKey: ["ledger", projectId],
    queryFn: async () =>
      (await api.get(`/api/budget/ledger/${projectId}`)).data,
    enabled: !!projectId,
    // fallback freshness if the websocket drops
    refetchInterval: 15000,
  });

  const [live, setLive] = useState<Ledger | null>(null);

  useEffect(() => {
    const socket = getSocket();
    socket.connect();
    socket.emit("join_project", { project_id: projectId });

    const handler = (payload: Ledger) => setLive(payload);
    socket.on("ledger:updated", handler);

    return () => {
      socket.off("ledger:updated", handler);
      // no socket.disconnect() — the socket is shared app-wide
    };
  }, [projectId]);

  return live ?? q.data ?? null;
}
