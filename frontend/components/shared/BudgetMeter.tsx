"use client";

import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { cn } from "@/lib/utils";

const VOUCHER = 40;

export function BudgetMeter({ projectId }: { projectId?: string }) {
  const { data } = useQuery({
    queryKey: ["budget-meter", projectId],
    queryFn: async () => {
      const { data } = await api.get(
        `/api/generate/project/${projectId}/latest`
      );
      return data as { actual_cost: number };
    },
    enabled: !!projectId,
    retry: false,
    refetchInterval: 4000,
  });

  const spent = data?.actual_cost ?? 0;
  const pct = Math.min((spent / VOUCHER) * 100, 100);
  const tone =
    pct > 85 ? "bg-bad" : pct > 70 ? "bg-warn" : "bg-primary";

  return (
    <div className="glass rounded-full pl-3 pr-1 py-1 flex items-center gap-2 min-w-[150px]">
      <div className="flex flex-col leading-none">
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          Voucher
        </span>
        <span className="text-xs font-semibold tabular-nums">
          ${spent.toFixed(2)}{" "}
          <span className="text-muted-foreground">/ ${VOUCHER}</span>
        </span>
      </div>
      <div className="h-7 w-px bg-border" />
      <div className="relative h-2 w-16 rounded-full bg-secondary overflow-hidden">
        <div
          className={cn("absolute inset-y-0 left-0 rounded-full transition-all", tone)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
