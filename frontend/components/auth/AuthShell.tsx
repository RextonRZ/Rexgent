"use client";

import Link from "next/link";

/** Centered glass card used by the login and signup screens. */
export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <main className="min-h-screen flex flex-col">
      <header className="border-b hairline">
        <div className="mx-auto max-w-6xl w-full px-6 h-14 flex items-center">
          <Link href="/">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/rexgent_wordmark.png"
              alt="Rexgent"
              className="h-4 w-auto"
            />
          </Link>
        </div>
      </header>

      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="text-center mb-6">
            <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
            {subtitle && (
              <p className="mt-1.5 text-sm text-muted-foreground">{subtitle}</p>
            )}
          </div>
          <div className="rounded-xl border hairline glass p-6">{children}</div>
          {footer && (
            <p className="mt-5 text-center text-sm text-muted-foreground">
              {footer}
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
