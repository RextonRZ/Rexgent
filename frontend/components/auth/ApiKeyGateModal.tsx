"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { KeyRound, ShieldCheck, Wallet, Sparkles } from "lucide-react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useApiKeyStatus, useSaveApiKey } from "@/hooks/useApiKey";
import { errText } from "@/lib/errText";

const DISMISS_KEY = "byok-prompt-dismissed";

/** First-run nudge: a signed-in user with no Qwen key gets an attractive
 *  modal inviting them to connect one. Shown once per session (dismissible),
 *  and again on a fresh login. Mounted inside AuthGate so it rides every
 *  protected page. Suppressed on the Settings page, which has its own field. */
export function ApiKeyGateModal() {
  const { data: status } = useApiKeyStatus();
  const save = useSaveApiKey();
  const pathname = usePathname();
  const [dismissed, setDismissed] = useState(true); // default hidden until we check

  useEffect(() => {
    // re-evaluate whenever the key status resolves
    if (typeof window === "undefined") return;
    setDismissed(sessionStorage.getItem(DISMISS_KEY) === "1");
  }, [status]);

  const [draft, setDraft] = useState("");

  const onSettings = pathname?.startsWith("/settings");
  const open =
    !!status && !status.configured && !onSettings && !dismissed && !save.isSuccess;

  const close = () => {
    if (typeof window !== "undefined") sessionStorage.setItem(DISMISS_KEY, "1");
    setDismissed(true);
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && close()}>
      <DialogContent className="max-w-md overflow-hidden p-0 gap-0">
        {/* header band */}
        <div className="relative overflow-hidden bg-gradient-to-br from-primary/25 via-primary/10 to-transparent px-6 pt-6 pb-5">
          <div className="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-primary/20 blur-2xl" />
          <div className="relative flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/20 text-primary glow">
              <KeyRound className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-lg font-semibold leading-tight">
                Connect your Qwen Cloud key
              </h2>
              <p className="text-xs text-muted-foreground">
                One step before your first drama
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-4 px-6 py-5">
          <p className="text-sm text-muted-foreground">
            Rexgent runs every model on{" "}
            <span className="text-foreground">your own</span> Qwen Cloud account,
            so you stay in full control of what you spend. Paste your key once and
            you are ready to create.
          </p>

          <div className="grid gap-2.5">
            <Benefit icon={<Wallet className="h-4 w-4" />} title="Your account, your spend">
              Every render bills your Qwen Cloud credit, never a shared bill.
            </Benefit>
            <Benefit icon={<ShieldCheck className="h-4 w-4" />} title="Stored encrypted">
              The key is encrypted at rest and shown only as its last four digits.
            </Benefit>
            <Benefit icon={<Sparkles className="h-4 w-4" />} title="Every model, priced">
              Writing, video, voice and vision — each call itemized before it runs.
            </Benefit>
          </div>

          <div className="space-y-2 pt-1">
            <input
              type="password"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Paste your DashScope API key (sk-...)"
              autoComplete="off"
              className="w-full rounded-lg border border-border bg-background/60 px-3 py-2.5 text-sm outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/40"
            />
            {save.isError && (
              <p className="text-xs text-bad">{errText(save.error)}</p>
            )}
            <p className="text-[11px] text-muted-foreground">
              Get a key from the{" "}
              <a
                href="https://modelstudio.console.alibabacloud.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                international Model Studio console
              </a>
              . It is validated against Qwen Cloud before it is saved.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 border-t hairline bg-white/[0.015] px-6 py-4">
          <Button
            className="flex-1 glow"
            onClick={() => save.mutate(draft)}
            disabled={!draft.trim() || save.isPending}
          >
            {save.isPending ? "Verifying…" : "Save & continue"}
          </Button>
          <Button variant="ghost" onClick={close} className="text-muted-foreground">
            Maybe later
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Benefit({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-2.5">
      <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
        {icon}
      </span>
      <div className="min-w-0">
        <p className="text-sm font-medium leading-tight">{title}</p>
        <p className="text-xs text-muted-foreground">{children}</p>
      </div>
    </div>
  );
}
