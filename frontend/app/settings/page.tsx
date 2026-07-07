"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { AuthGate } from "@/components/auth/AuthGate";
import { UserMenu } from "@/components/auth/UserMenu";
import { useAuth, useLogout } from "@/hooks/useAuth";

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
            <span className="text-base">←</span>
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

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-3">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium">{value}</dd>
    </div>
  );
}
