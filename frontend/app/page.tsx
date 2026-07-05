"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { BTN_PRIMARY, BTN_SECONDARY, CtaArrow } from "@/components/ui/cta";
import { FilmstripHero } from "@/components/landing/FilmstripHero";
import { ShowreelGallery } from "@/components/landing/ShowreelGallery";
import { FeatureBento } from "@/components/landing/FeatureBento";
import { CtaBackdrop } from "@/components/landing/CtaBackdrop";
import { useAuth } from "@/hooks/useAuth";

function scrollToReel() {
  const el = document.getElementById("reel");
  if (!el) return;
  const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
}

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
          <nav className="flex items-center gap-6">
            {isAuthenticated ? (
              <Link href="/projects">
                <Button className={`h-10 ${BTN_PRIMARY}`}>
                  Your dramas
                  <CtaArrow />
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
                  <Button className={`h-10 ${BTN_PRIMARY}`}>
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
              Rexgent writes the script, casts your characters with faces that
              never drift, storyboards every scene, generates each clip, and
              delivers a finished captioned film, all within a budget you can
              watch in real time.
            </p>
            <div className="mt-8 flex items-center justify-center md:justify-start gap-3">
              <Link href={isAuthenticated ? "/projects" : "/signup"}>
                <Button
                  className={`h-12 text-base ${BTN_PRIMARY} shadow-[0_0_24px_rgba(139,92,246,0.35)]`}
                >
                  {isAuthenticated ? "Open your studio" : "Start directing"}
                  <CtaArrow />
                </Button>
              </Link>
              <Button
                variant="outline"
                className={`h-12 text-base ${BTN_SECONDARY}`}
                onClick={scrollToReel}
              >
                <Play className="size-3.5" />
                Watch the reel
              </Button>
            </div>
          </div>

          {/* right: vertical curved filmstrip feeding through 5 episodes */}
          <FilmstripHero />
        </div>
      </section>

      <ShowreelGallery />

      {/* wow moments — bento grid */}
      <FeatureBento />

      {/* final CTA */}
      <section id="cta" className="relative overflow-hidden py-32 text-center">
        <CtaBackdrop />
        <div className="relative z-10 mx-auto max-w-2xl px-6">
          <p className="text-xs uppercase tracking-[0.3em] text-primary/80 mb-4">
            Ready when you are
          </p>
          <h2 className="text-4xl sm:text-5xl font-bold tracking-tight">
            Your first drama is one idea away.
          </h2>
          <p className="mt-4 text-muted-foreground">
            Type a premise. Watch a studio go to work.
          </p>
          <div className="mt-8 flex items-center justify-center gap-3">
            <Link href={isAuthenticated ? "/projects" : "/signup"}>
              <Button
                className={`h-12 text-base ${BTN_PRIMARY} shadow-[0_0_24px_rgba(139,92,246,0.35)]`}
              >
                {isAuthenticated ? "Open your studio" : "Start directing"}
                <CtaArrow />
              </Button>
            </Link>
            <Button
              variant="outline"
              className={`h-12 text-base ${BTN_SECONDARY}`}
              onClick={scrollToReel}
            >
              <Play className="size-3.5" />
              Watch the reel
            </Button>
          </div>
        </div>
      </section>

      <footer className="border-t border-white/[0.08]">
        <div className="mx-auto flex max-w-7xl flex-col items-center gap-6 px-6 py-10 text-xs text-muted-foreground md:flex-row md:justify-between">
          <div className="flex items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/rexgent_wordmark.png"
              alt="Rexgent"
              className="h-4 w-auto"
            />
            <span>AI Drama Production</span>
          </div>
          <nav className="flex items-center gap-6">
            <a
              href="#features"
              className="transition-colors hover:text-foreground"
            >
              How it works
            </a>
            <a href="#reel" className="transition-colors hover:text-foreground">
              Reel
            </a>
            <a href="#" className="transition-colors hover:text-foreground">
              Pricing
            </a>
            <a
              href="mailto:ooiruizhe@gmail.com"
              className="transition-colors hover:text-foreground"
            >
              Contact
            </a>
          </nav>
          <div className="flex flex-col items-center gap-1 md:items-end">
            <span>Built on Qwen Cloud · Alibaba Cloud</span>
            <span>© 2026 Rexgent</span>
          </div>
        </div>
      </footer>
    </main>
  );
}
