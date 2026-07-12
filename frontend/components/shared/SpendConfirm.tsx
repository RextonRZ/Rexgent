"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

/** One priced line of a spend, e.g. "Costume plates ... $0.60". */
export interface SpendItem {
  label: string;
  /** what produces it: counts and model names */
  detail?: string;
  amount: number;
}

/** A tickable extra on a paid action, priced on its own line. */
export interface SpendOption {
  key: string;
  /** what the tick buys, e.g. "Design a bespoke voice for this character" */
  label: string;
  /** its price stated plainly, e.g. "$0.20 once" or "free" */
  priceLine: string;
  /** one plain sentence of context under the label */
  note?: string;
  defaultOn?: boolean;
  /** counted into the total while ticked */
  amount?: number;
}

/** What a paid click is about to do, priced, awaiting a yes. */
export interface SpendRequest {
  title: string;
  /** a COMPLETE sentence stating the price, e.g.
   * "This costs about $0.08 of your credit." */
  costLine: string;
  /** what happens, one plain sentence */
  note?: string;
  confirmLabel?: string;
  /** itemized fixed costs, each with the model behind it */
  breakdown?: SpendItem[];
  /** optional priced extras the user ticks on or off before confirming */
  options?: SpendOption[];
  run: (choices?: Record<string, boolean>) => void;
}

/** The paid-action gate: nothing that spends the voucher runs off a bare
 * click — a small modal states the price first. With a breakdown it itemizes
 * every model and shows a live total that follows the ticks. Controlled by
 * the caller: pass the pending request (or null) and a setter to clear it. */
export function SpendConfirm({
  request,
  onClose,
}: {
  request: SpendRequest | null;
  onClose: () => void;
}) {
  const [choices, setChoices] = useState<Record<string, boolean>>({});

  // a fresh request resets the ticks to its defaults
  useEffect(() => {
    if (request?.options) {
      setChoices(
        Object.fromEntries(request.options.map((o) => [o.key, o.defaultOn ?? true]))
      );
    } else {
      setChoices({});
    }
  }, [request]);

  const hasBreakdown = !!request?.breakdown?.length;
  const total =
    (request?.breakdown?.reduce((s, i) => s + i.amount, 0) ?? 0) +
    (request?.options?.reduce(
      (s, o) => s + ((choices[o.key] ?? o.defaultOn ?? true) ? o.amount ?? 0 : 0),
      0
    ) ?? 0);

  return (
    <Dialog open={!!request} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{request?.title}</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          <span className="text-foreground">{request?.costLine}</span>
          {request?.note ? ` ${request.note}` : ""}
        </p>
        {hasBreakdown && (
          <div className="divide-y divide-border rounded-md border hairline bg-background/40 text-xs">
            {request!.breakdown!.map((item) => (
              <div key={item.label} className="flex items-start justify-between gap-2 p-2">
                <span className="min-w-0">
                  <span className="block text-foreground">{item.label}</span>
                  {item.detail && (
                    <span className="block text-[10px] text-muted-foreground">
                      {item.detail}
                    </span>
                  )}
                </span>
                <span className="shrink-0 text-foreground">${item.amount.toFixed(2)}</span>
              </div>
            ))}
          </div>
        )}
        {request?.options?.map((o) => (
          <label
            key={o.key}
            className="flex cursor-pointer items-start gap-2 rounded-md border hairline bg-background/40 p-2"
          >
            <input
              type="checkbox"
              checked={choices[o.key] ?? true}
              onChange={(e) =>
                setChoices((c) => ({ ...c, [o.key]: e.target.checked }))
              }
              className="mt-0.5 accent-[var(--primary)]"
            />
            <span className="min-w-0 flex-1 text-xs leading-snug">
              <span className="flex items-center justify-between gap-2">
                <span className="text-foreground">{o.label}</span>
                <span className="shrink-0 text-primary">{o.priceLine}</span>
              </span>
              {o.note && <span className="text-muted-foreground">{o.note}</span>}
            </span>
          </label>
        ))}
        {(hasBreakdown || request?.options?.some((o) => o.amount)) && (
          <div className="flex items-center justify-between px-2 text-sm">
            <span className="text-muted-foreground">Total</span>
            <span className="font-semibold text-foreground">≈ ${total.toFixed(2)}</span>
          </div>
        )}
        <div className="flex gap-2 pt-1">
          <Button
            variant="outline"
            className="flex-1"
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button
            className="flex-1"
            onClick={() => {
              request?.run(choices);
              onClose();
            }}
          >
            {request?.confirmLabel ?? "Continue"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
