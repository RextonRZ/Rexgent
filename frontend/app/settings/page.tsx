"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { AuthGate } from "@/components/auth/AuthGate";
import { UserMenu } from "@/components/auth/UserMenu";
import { useAuth, useLogout } from "@/hooks/useAuth";
import { useApiKeyStatus, useSaveApiKey, useDeleteApiKey } from "@/hooks/useApiKey";
import { errText } from "@/lib/errText";

const PERSONA_LABEL: Record<string, string> = {
  creator: "Solo creator",
  studio: "Content studio",
  brand: "Brand / marketing",
  student: "Film student",
};

export default function SettingsPage() {
  return (
    <AuthGate>
      <Settings />
    </AuthGate>
  );
}

function Settings() {
  const { user } = useAuth();
  const logout = useLogout();

  const memberSince = user?.created_at
    ? new Date(user.created_at).toLocaleDateString(undefined, {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "—";

  return (
    <main className="min-h-screen">
      <header className="sticky top-0 z-40 glass border-b hairline">
        <div className="mx-auto max-w-3xl px-6 h-14 flex items-center justify-between">
          <Link
            href="/projects"
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/rexgent_wordmark.png"
              alt="Rexgent"
              className="h-4 w-auto"
            />
          </Link>
          <UserMenu />
        </div>
      </header>

      <div className="mx-auto max-w-3xl px-6 py-10 space-y-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
          <p className="text-sm text-muted-foreground">
            Your account and studio preferences.
          </p>
        </div>

        {/* Account */}
        <section className="rounded-xl border hairline bg-card p-6">
          <h2 className="text-sm font-medium mb-4">Account</h2>
          <dl className="divide-y hairline">
            <Row label="Name" value={user?.full_name || "—"} />
            <Row label="Email" value={user?.email || "—"} />
            <Row
              label="I am a"
              value={
                user?.persona ? PERSONA_LABEL[user.persona] || user.persona : "—"
              }
            />
            <Row label="Member since" value={memberSince} />
          </dl>
        </section>

        {/* Bring your own key */}
        <ApiKeySection />

        {/* Danger / session */}
        <section className="rounded-xl border hairline bg-card p-6 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-medium">Session</h2>
            <p className="text-sm text-muted-foreground">
              Sign out of this device.
            </p>
          </div>
          <Button variant="outline" onClick={logout} className="text-bad">
            Sign out
          </Button>
        </section>
      </div>
    </main>
  );
}

function ApiKeySection() {
  const { data: status } = useApiKeyStatus();
  const save = useSaveApiKey();
  const remove = useDeleteApiKey();
  const [draft, setDraft] = useState("");

  return (
    <section className="rounded-xl border hairline bg-card p-6 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium">Qwen API key</h2>
          <p className="text-sm text-muted-foreground">
            Your dramas bill your own Qwen Cloud account. Get a key from the
            international Model Studio console, then paste it here. It is
            stored encrypted and never shown again.
          </p>
        </div>
        {status?.configured ? (
          <span className="shrink-0 rounded-full bg-ok/15 px-2.5 py-1 text-xs text-ok">
            Active ····{status.tail}
          </span>
        ) : status?.required ? (
          <span className="shrink-0 rounded-full bg-bad/15 px-2.5 py-1 text-xs text-bad">
            Required
          </span>
        ) : (
          <span className="shrink-0 rounded-full bg-secondary px-2.5 py-1 text-xs text-muted-foreground">
            Not set
          </span>
        )}
      </div>

      {status?.required && !status?.configured && (
        <p className="rounded-md border border-bad/30 bg-bad/10 p-3 text-xs text-bad">
          This deployment requires your own key: nothing paid will run until
          you add one. Create a key at the Alibaba Cloud Model Studio console
          (international / Singapore region).
        </p>
      )}

      <div className="flex gap-2">
        <input
          type="password"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="sk-..."
          autoComplete="off"
          className="flex-1 rounded-md border border-border bg-background/60 px-3 py-2 text-sm"
        />
        <Button
          onClick={() => save.mutate(draft, { onSuccess: () => setDraft("") })}
          disabled={!draft.trim() || save.isPending}
        >
          {save.isPending ? "Checking…" : status?.configured ? "Replace" : "Save"}
        </Button>
        {status?.configured && (
          <Button
            variant="outline"
            onClick={() => remove.mutate()}
            disabled={remove.isPending}
            className="text-bad"
          >
            Remove
          </Button>
        )}
      </div>
      {save.isError && (
        <p className="text-xs text-bad">{errText(save.error)}</p>
      )}
      {save.isSuccess && !save.isPending && (
        <p className="text-xs text-ok">
          Key verified against Qwen Cloud and saved. Every paid action now
          bills this key.
        </p>
      )}
      {!status?.required && status?.server_fallback && !status?.configured && (
        <p className="text-xs text-muted-foreground">
          Without a personal key this instance falls back to the server key,
          which is fine for local development.
        </p>
      )}
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-3">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium">{value}</dd>
    </div>
  );
}
