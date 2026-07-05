"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FilmstripHero } from "@/components/landing/FilmstripHero";
import { ShowreelGallery } from "@/components/landing/ShowreelGallery";
import { useAuth } from "@/hooks/useAuth";

// One button system for the whole page. Flat brand violet, shared radius and
// timing; translate animations only when motion is allowed.
const BTN_PRIMARY =
  "rounded-xl px-6 font-medium bg-violet-500 text-white " +
  "transition-all duration-200 hover:bg-violet-400 " +
  "motion-safe:hover:-translate-y-px active:translate-y-0 active:bg-violet-600 " +
  "focus-visible:ring-2 focus-visible:ring-violet-400/60 " +
  "focus-visible:ring-offset-2 focus-visible:ring-offset-black";

const BTN_SECONDARY =
  "rounded-xl px-6 font-medium bg-transparent dark:bg-transparent " +
  "border-white/15 dark:border-white/15 text-zinc-200 " +
  "transition-all duration-200 " +
  "hover:border-white/30 dark:hover:border-white/30 " +
  "hover:bg-white/5 dark:hover:bg-white/5 hover:text-zinc-100";

// trailing arrow that nudges right on button hover
function CtaArrow() {
  return (
    <ArrowRight className="size-4 transition-transform duration-200 motion-safe:group-hover/button:translate-x-[3px]" />
  );
}

const WOWS = [
  {
    k: "01",
    title: "One premise, a whole drama",
    body: "An autonomous agent writes the script, judges its own draft, casts the characters, storyboards every scene and reports back. You watch a studio work for you.",
  },
  {
    k: "02",
    title: "Faces that never drift",
    body: "Upload one reference photo. Every clip is verified against a real facial embedding, and weak takes retry themselves until the face holds.",
  },
  {
    k: "03",
    title: "Wardrobe built in",
    body: "Every character gets costume plates for each look in the story, so the same person walks through every scene wearing the right outfit.",
  },
  {
    k: "04",
    title: "Clone your voice",
    body: "Read one short passage into your mic and your characters speak with your voice, or pick from a catalog of studio presets.",
  },
  {
    k: "05",
    title: "You stay the director",
    body: "Edit the script, swap faces, redo plates, delete shots, regenerate clips. The agent runs the pipeline while you keep creative control.",
  },
  {
    k: "06",
    title: "The budget is a feature",
    body: "A live meter spends premium generation only on the shots that matter, turning a hard limit into a smart allocator.",
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
                    <CtaArrow />
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
                onClick={() => {
                  const el = document.getElementById("reel");
                  if (!el) return;
                  const smooth = !window.matchMedia(
                    "(prefers-reduced-motion: reduce)"
                  ).matches;
                  el.scrollIntoView({
                    behavior: smooth ? "smooth" : "auto",
                    block: "start",
                  });
                }}
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
