"use client";

import Link from "next/link";

/** Shared studio footer for the app pages — a filmstrip hairline, the
 * wordmark, quick links and the Qwen Cloud credit, echoing the landing page. */
export function SiteFooter() {
  return (
    <footer className="relative mt-16 border-t border-white/[0.08]">
      {/* thin sprocket strip so the footer reads as the reel's tail */}
      <div
        aria-hidden
        className="flex justify-center gap-2 py-1.5 opacity-40"
      >
        {Array.from({ length: 24 }).map((_, i) => (
          <span key={i} className="h-[4px] w-[3px] rounded-[1px] bg-white/25" />
        ))}
      </div>
      <div className="mx-auto flex max-w-7xl flex-col items-center gap-5 px-6 py-8 text-xs text-muted-foreground md:flex-row md:justify-between">
        <div className="flex items-center gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/rexgent_wordmark.png" alt="Rexgent" className="h-4 w-auto" />
          <span className="text-zinc-500">AI Drama Production</span>
        </div>
        <nav className="flex items-center gap-6">
          <Link href="/projects" className="transition-colors hover:text-foreground">
            Your dramas
          </Link>
          <Link href="/" className="transition-colors hover:text-foreground">
            Home
          </Link>
          <a
            href="mailto:ooiruizhe@gmail.com"
            className="transition-colors hover:text-foreground"
          >
            Contact
          </a>
        </nav>
        <div className="flex flex-col items-center gap-1 md:items-end">
          <span>Built on Qwen Cloud · Alibaba Cloud</span>
          <span className="text-zinc-600">© 2026 Rexgent</span>
        </div>
      </div>
    </footer>
  );
}
