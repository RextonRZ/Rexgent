"use client";

import { useGenerationStore } from "@/stores/generationStore";
import { cn } from "@/lib/utils";

const VOUCHER = 40;

export function CostTracker() {
  const currentCost = useGenerationStore((s) => s.currentCost);
  const pct = Math.min((currentCost / VOUCHER) * 100, 100);
  const tone = pct > 85 ? "bg-bad" : pct > 70 ? "bg-warn" : "bg-primary";

  return (
    <div className="glass rounded-xl p-5">
      <div className="flex items-end justify-between">
        <div>
          <p className="text-xs uppercase tracking-widest text-muted-foreground">
            Live cost
          </p>
          <p className="text-3xl font-bold tabular-nums mt-1">
            ${currentCost.toFixed(2)}
            <span className="text-base font-normal text-muted-foreground">
              {" "}
              / ${VOUCHER.toFixed(2)}
            </span>
          </p>
        </div>
        <span
          className={cn(
            "text-xs font-medium px-2 py-1 rounded-full",
            pct > 85
              ? "bg-bad/15 text-bad"
              : pct > 70
              ? "bg-warn/15 text-warn"
              : "bg-primary/15 text-primary"
          )}
        >
          {pct.toFixed(0)}% of voucher
        </span>
      </div>
      <div className="mt-4 h-2.5 rounded-full bg-secondary overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-500", tone)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
