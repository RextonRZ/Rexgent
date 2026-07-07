"use client";

import Link from "next/link";
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
            {/* left: wordmark — click returns to the dashboard */}
            <Link
              href="/projects"
              aria-label="Back to dashboard"
              title="Back to dashboard"
              className="shrink-0 rounded transition-opacity hover:opacity-80"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/rexgent_wordmark.png"
                alt="Rexgent"
                className="h-4 w-auto"
              />
            </Link>

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
