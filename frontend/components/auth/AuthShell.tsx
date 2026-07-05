"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Eye, EyeOff } from "lucide-react";
import { cn } from "@/lib/utils";

// Shared field styling so both auth pages stay identical siblings.
export const FIELD =
  "h-11 w-full rounded-lg border border-white/10 bg-zinc-900 px-4 text-sm " +
  "placeholder:text-zinc-500 outline-none transition-colors " +
  "focus:border-violet-500 focus:ring-2 focus:ring-violet-500/25";
export const FIELD_ERROR = "border-red-500/50";
export const LABEL = "mb-1.5 block text-sm text-zinc-300";

// One of these lights the right panel per page load. Full-quality clips —
// only one loads per visit, and the panel is too large for the small previews.
const PANEL_SHOTS = [
  { ep: 1, title: "A Chance Encounter", poster: "/poster1.jpg", video: "/clip1.mp4" },
  { ep: 2, title: "First Spark", poster: "/poster5.jpg", video: "/clip5.mp4" },
  { ep: 3, title: "Lakeside Melody", poster: "/poster7.jpg", video: "/clip7.mp4" },
  { ep: 4, title: "Before Goodbye", poster: "/poster9.jpg", video: "/clip9.mp4" },
  { ep: 5, title: "Stars Remember", poster: "/poster12.jpg", video: "/clip12.mp4" },
];

function SprocketColumn({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "absolute inset-y-0 flex flex-col items-center justify-evenly opacity-40",
        className
      )}
    >
      {Array.from({ length: 22 }).map((_, i) => (
        <span key={i} className="h-[10px] w-[8px] rounded-[2px] bg-white/25" />
      ))}
    </div>
  );
}

/** Password input with a visibility toggle. */
export function PasswordField({
  id,
  value,
  onChange,
  placeholder,
  autoComplete,
  error,
  autoFocus,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  autoComplete?: string;
  error?: boolean;
  autoFocus?: boolean;
}) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <input
        id={id}
        type={show ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        autoFocus={autoFocus}
        required
        className={cn(FIELD, "pr-11", error && FIELD_ERROR)}
      />
      <button
        type="button"
        aria-label={show ? "Hide password" : "Show password"}
        onClick={() => setShow((s) => !s)}
        className="absolute right-3 top-1/2 -translate-y-1/2 rounded text-zinc-500 outline-none transition-colors hover:text-zinc-300 focus-visible:ring-2 focus-visible:ring-violet-500/40"
      >
        {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </div>
  );
}

/** Quiet alert row for general auth errors; always mounted so it announces. */
export function AuthAlert({ message }: { message: string | null }) {
  return (
    <div aria-live="polite">
      {message && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-400">
          {message}
        </div>
      )}
    </div>
  );
}

/** Split-screen auth layout: form column left, cinematic still right. */
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
  // Random pick happens after mount so server and client render agree.
  const [shot, setShot] = useState<(typeof PANEL_SHOTS)[number] | null>(null);
  useEffect(() => {
    setShot(PANEL_SHOTS[Math.floor(Math.random() * PANEL_SHOTS.length)]);
  }, []);

  return (
    <main className="min-h-screen lg:grid lg:grid-cols-[45fr_55fr]">
      {/* form column */}
      <div className="flex min-h-screen flex-col px-6 py-6 sm:px-10">
        <Link href="/" className="self-start">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/rexgent_wordmark.png"
            alt="Rexgent"
            className="h-4 w-auto"
          />
        </Link>
        <div className="flex flex-1 items-center">
          <div className="mx-auto w-full max-w-sm">
            <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
            {subtitle && (
              <p className="mt-1.5 text-sm text-muted-foreground">{subtitle}</p>
            )}
            <div className="mt-6 rounded-2xl border border-white/[0.08] bg-white/[0.02] p-8">
              {children}
            </div>
            {footer && (
              <p className="mt-5 text-sm text-muted-foreground">{footer}</p>
            )}
          </div>
        </div>
      </div>

      {/* cinematic panel */}
      <div className="relative hidden overflow-hidden bg-zinc-950 lg:block">
        {shot && (
          <>
            <video
              src={shot.video}
              poster={shot.poster}
              muted
              loop
              playsInline
              autoPlay
              preload="metadata"
              className="absolute inset-0 h-full w-full object-cover brightness-75"
            />
            <div className="absolute bottom-4 left-4 flex items-center gap-1.5 rounded-full bg-black/60 px-2.5 py-1 text-[11px] text-white/90 backdrop-blur-sm">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red-500" />
              <span>
                <span className="font-medium text-primary">EP {shot.ep}</span> ·{" "}
                {shot.title} — generated by Rexgent
              </span>
            </div>
          </>
        )}
        {/* film chrome on the panel edges */}
        <SprocketColumn className="left-3" />
        <SprocketColumn className="right-3" />
      </div>
    </main>
  );
}
