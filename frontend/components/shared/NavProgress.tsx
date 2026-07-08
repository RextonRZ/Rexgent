"use client";

import { useEffect, useRef, useTransition } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { create } from "zustand";
import { useReducedMotion } from "@/hooks/useReducedMotion";

/** ── instant navigation feedback ─────────────────────────────────────────
 * Route skeletons appear once the next page starts rendering — but between
 * the CLICK and that moment there was dead air. Navigations run inside a
 * React transition here, and a violet hairline progress bar shows the very
 * frame the click lands, until the destination (or its loading skeleton)
 * commits. Nothing ever feels hung.
 */

const useNavPending = create<{ n: number; start: () => void; end: () => void }>(
  (set) => ({
    n: 0,
    start: () => set((s) => ({ n: s.n + 1 })),
    end: () => set((s) => ({ n: Math.max(0, s.n - 1) })),
  })
);

/** Navigate with click-time feedback: `const go = useGo(); go(href)`. */
export function useGo() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const start = useNavPending((s) => s.start);
  const end = useNavPending((s) => s.end);
  const active = useRef(false);

  useEffect(() => {
    if (isPending && !active.current) {
      active.current = true;
      start();
    } else if (!isPending && active.current) {
      active.current = false;
      end();
    }
    return () => {
      if (active.current) {
        active.current = false;
        end();
      }
    };
  }, [isPending, start, end]);

  return (href: string) => startTransition(() => router.push(href));
}

/** Drop-in next/link replacement: keeps prefetch + open-in-new-tab, but the
 * plain left-click navigates through the transition so the bar shows. */
export function GoLink({
  href,
  children,
  className,
  ...rest
}: React.ComponentProps<typeof Link>) {
  const go = useGo();
  return (
    <Link
      href={href}
      className={className}
      {...rest}
      onClick={(e) => {
        rest.onClick?.(e);
        if (e.defaultPrevented) return;
        // let modified clicks (new tab, etc.) behave natively
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0)
          return;
        e.preventDefault();
        go(typeof href === "string" ? href : String(href));
      }}
    >
      {children}
    </Link>
  );
}

/** The bar itself — mount once in the root layout. */
export function NavProgress() {
  const pending = useNavPending((s) => s.n > 0);
  const reduced = useReducedMotion();
  const pathname = usePathname();
  // backstop: a committed route change always clears the bar
  useEffect(() => {
    useNavPending.setState({ n: 0 });
  }, [pathname]);

  if (!pending) return null;
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-x-0 top-0 z-[100] h-[2px] overflow-hidden bg-violet-500/15"
    >
      <div
        className={reduced ? "h-full w-full bg-violet-400/80" : "h-full w-1/3 rounded-full bg-violet-400 animate-[nav-slide_0.9s_ease-in-out_infinite]"}
        style={{ boxShadow: "0 0 12px rgba(167,139,250,0.8)" }}
      />
    </div>
  );
}
