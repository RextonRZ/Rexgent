"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

/** What a paid click is about to do, priced, awaiting a yes. */
export interface SpendRequest {
  title: string;
  /** a COMPLETE sentence stating the price, e.g.
   * "This costs about $0.08 of your credit." */
  costLine: string;
  /** what happens, one plain sentence */
  note?: string;
  confirmLabel?: string;
  run: () => void;
}

/** The paid-action gate: nothing that spends the voucher runs off a bare
 * click — a small modal states the price first. Controlled by the caller:
 * pass the pending request (or null) and a setter to clear it. */
export function SpendConfirm({
  request,
  onClose,
}: {
  request: SpendRequest | null;
  onClose: () => void;
}) {
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
              request?.run();
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
