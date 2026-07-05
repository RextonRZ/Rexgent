"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { FilmstripHero } from "@/components/landing/FilmstripHero";
import { ShowreelGallery } from "@/components/landing/ShowreelGallery";
import { useAuth } from "@/hooks/useAuth";

// Same gradient as the filmstrip timeline's active cell, plus a soft
// lift + glow on hover.
const CTA_GRADIENT =
  "bg-gradient-to-r from-violet-500 to-purple-500 text-black font-semibold " +
  "transition-all duration-300 " +
  "hover:brightness-110 hover:-translate-y-0.5 hover:shadow-[0_0_28px_hsl(265_85%_66%/0.45)]";

const WOWS = [
  {
    k: "01",
    title: "One premise → a whole drama",
    body: "An autonomous agent writes the script, casts it, storyboards it, generates it, and reports back. You watch a studio work for you.",
  },
  {
    k: "02",
    title: "Faces that don't drift",
    body: "Upload one reference photo. Every clip is verified frame-by-frame against a real facial embedding, with self-correcting retries.",
  },
  {
    k: "03",
    title: "The budget is a feature",
    body: "A live meter spends premium generation only on the shots that matter — turning a hard limit into a smart allocator.",
  },
];

export default function LandingPage() {
  const { isAuthenticated: authed } = useAuth();
  // Persisted auth only resolves on the client; default to signed-out for SSR
  // to avoid a hydration mismatch, then reveal the real state after mount.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const isAuthenticated = mounted && authed;

  return (
    <main className="min-h-screen">
      <header className="border-b hairline">
        <div className="mx-auto max-w-7xl px-6 h-16 flex items-center justify-between">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/rexgent_wordmark.png"
            alt="Rexgent"
            className="h-4 w-auto"
          />
          <nav className="flex items-center gap-3">
            {isAuthenticated ? (
              <Link href="/projects">
                <Button size="sm" className="glow">
                  Your dramas →
                </Button>
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  Sign in
                </Link>
                <Link href="/signup">
                  <Button
                    size="sm"
                    className={`rounded-lg px-5 leading-none ${CTA_GRADIENT}`}
                  >
                    Get started
                  </Button>
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      {/* hero — split: copy left, curved filmstrip showcase right */}
      <section className="mx-auto max-w-7xl px-6">
        <div className="grid items-center gap-10 pt-16 pb-16 sm:pt-24 md:min-h-[calc(100vh-4rem)] md:grid-cols-[10fr_9fr] md:gap-16 md:py-10">
          {/* left: copy + CTAs */}
          <div className="text-center md:text-left">
            <p className="text-xs uppercase tracking-[0.3em] text-primary/80 mb-4">
              AI Showrunner · Qwen Cloud
            </p>
            <h1 className="text-4xl sm:text-5xl xl:text-6xl font-bold tracking-tight">
              Give me a story idea. I&apos;ll hand you back a{" "}
              <span className="text-gradient">short drama</span>.
            </h1>
            <p className="mt-5 text-muted-foreground max-w-xl mx-auto md:mx-0">
              Rexgent writes it, casts it with locked facial identity,
              storyboards it, generates the clips, and exports a captioned film, 
              all on a fixed budget you can watch in real time.
            </p>
            <div className="mt-8 flex items-center justify-center md:justify-start gap-3">
              <Link href={isAuthenticated ? "/projects" : "/signup"}>
                <Button
                  size="lg"
                  className={`h-11 px-6 text-base ${CTA_GRADIENT}`}
                >
                  {isAuthenticated ? "Open your studio" : "Start directing"}
                </Button>
              </Link>
              {!isAuthenticated && (
                <Link href="/login">
                  <Button
                    size="lg"
                    variant="outline"
                    className="h-11 px-6 text-base border-white/90 dark:border-white/90 transition-all duration-300 hover:-translate-y-0.5 hover:border-white dark:hover:border-white hover:bg-primary/10 dark:hover:bg-primary/10 hover:shadow-[0_0_20px_hsl(265_85%_66%/0.25)]"
                  >
                    Sign in
                  </Button>
                </Link>
              )}
            </div>
          </div>

          {/* right: vertical curved filmstrip feeding through 5 episodes */}
          <FilmstripHero />
        </div>
      </section>

      <ShowreelGallery />

      {/* wow moments */}
      <section className="mx-auto max-w-6xl px-6 pb-28">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {WOWS.map((w) => (
            <div
              key={w.k}
              className="rounded-xl border hairline bg-card p-6 hover:border-primary/40 transition-all"
            >
              <span className="text-xs font-mono text-primary/70">{w.k}</span>
              <h3 className="mt-3 font-semibold">{w.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                {w.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t hairline">
        <div className="mx-auto max-w-7xl px-6 h-14 flex items-center justify-between text-xs text-muted-foreground">
          <span>Rexgent — AI Drama Production</span>
          <span>Built on Qwen Cloud · Alibaba Cloud</span>
        </div>
      </footer>
    </main>
  );
}
