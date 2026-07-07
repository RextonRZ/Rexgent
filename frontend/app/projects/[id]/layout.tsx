"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { PipelineNav } from "@/components/shared/PipelineNav";
import { AuthGate } from "@/components/auth/AuthGate";
import { UserMenu } from "@/components/auth/UserMenu";
import { DockRail } from "@/components/shared/DockRail";
import { AmbientBackdrop } from "@/components/shared/AmbientBackdrop";
import { SiteFooter } from "@/components/shared/SiteFooter";

export default function ProjectLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { id: string };
}) {
  return (
    <AuthGate>
      <div className="relative min-h-screen">
        <AmbientBackdrop />
        <header className="sticky top-0 z-40 glass border-b hairline">
          <div className="mx-auto max-w-7xl px-4 h-14 flex items-center justify-between gap-3">
            {/* left: back action · divider · wordmark */}
            <div className="flex items-center gap-2 sm:gap-3 shrink-0">
              <Link
                href="/projects"
                title="Back to dashboard"
                className="flex h-9 items-center gap-1.5 rounded-lg px-2 text-sm text-muted-foreground transition-colors hover:bg-white/5 hover:text-foreground sm:px-2.5"
              >
                <ArrowLeft className="size-4 shrink-0" />
                <span className="hidden sm:inline">Dashboard</span>
              </Link>
              <span className="h-5 w-px bg-white/10" aria-hidden />
              <Link href="/projects" aria-label="Rexgent home" className="shrink-0">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/rexgent_wordmark.png"
                  alt="Rexgent"
                  className="h-4 w-auto"
                />
              </Link>
            </div>

            {/* center: pipeline stepper (full on lg+, compact below) */}
            <PipelineNav projectId={params.id} />

            <div className="flex items-center gap-4 shrink-0">
              <UserMenu />
            </div>
          </div>
        </header>

        {/* content + right dock: the dock reflows the page, never overlaps it */}
        <div className="flex items-start gap-4">
          <main className="flex-1 min-w-0 px-6 lg:px-10 py-8">
            <div className="mx-auto max-w-7xl">{children}</div>
            <div className="mx-auto max-w-7xl">
              <SiteFooter />
            </div>
          </main>
          <DockRail projectId={params.id} />
        </div>
      </div>
    </AuthGate>
  );
}
