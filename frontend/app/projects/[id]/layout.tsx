"use client";

import Link from "next/link";
import { PipelineNav } from "@/components/shared/PipelineNav";
import { BudgetMeter } from "@/components/shared/BudgetMeter";

export default function ProjectLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { id: string };
}) {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 glass border-b hairline">
        <div className="mx-auto max-w-7xl px-4 h-14 flex items-center justify-between gap-4">
          <Link
            href="/"
            className="flex items-center gap-2 shrink-0 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <span className="text-base">←</span>
            <span className="font-semibold text-foreground">Rexgent</span>
          </Link>

          <div className="hidden sm:block">
            <PipelineNav projectId={params.id} />
          </div>

          <BudgetMeter projectId={params.id} />
        </div>
        {/* mobile pipeline nav */}
        <div className="sm:hidden border-t hairline px-4 py-2 overflow-x-auto">
          <PipelineNav projectId={params.id} />
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8">{children}</main>
    </div>
  );
}
