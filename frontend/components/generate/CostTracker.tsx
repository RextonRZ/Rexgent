"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useGenerationStore } from "@/stores/generationStore";

const VOUCHER = 40;

export function CostTracker() {
  const currentCost = useGenerationStore((s) => s.currentCost);
  const pct = Math.min((currentCost / VOUCHER) * 100, 100);

  return (
    <Card>
      <CardContent className="pt-4 space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">Live cost</span>
          <span>
            ${currentCost.toFixed(2)} / ${VOUCHER.toFixed(2)}
          </span>
        </div>
        <Progress value={pct} />
      </CardContent>
    </Card>
  );
}
