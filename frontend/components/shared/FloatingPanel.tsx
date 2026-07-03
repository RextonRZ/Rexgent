"use client";

import { useEffect, useState } from "react";

type Side = "bottom-right" | "top-right";

/** A pill that expands into a bounded, dockable panel. Open state is persisted. */
export function FloatingPanel({
  side,
  pill,
  title,
  storageKey,
  topOffset = 0,
  width = 300,
  children,
}: {
  side: Side;
  pill: React.ReactNode; // content of the collapsed pill
  title: string;
  storageKey: string; // localStorage key for open state
  topOffset?: number; // px from top (top-right panels open below the nav)
  width?: number;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(localStorage.getItem(storageKey) === "1");
  }, [storageKey]);

  const toggle = () =>
    setOpen((o) => {
      const next = !o;
      localStorage.setItem(storageKey, next ? "1" : "0");
      return next;
    });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const anchor: React.CSSProperties =
    side === "bottom-right"
      ? { bottom: 16, right: 16 }
      : { top: topOffset + 12, right: 16 };

  return (
    <div className="fixed z-40" style={anchor}>
      {open ? (
        <div
          className="glass rounded-xl shadow-2xl overflow-hidden flex flex-col"
          style={{ width, maxHeight: "70vh" }}
        >
          <div className="flex items-center justify-between px-3 py-2 border-b hairline shrink-0">
            <span className="text-xs font-semibold">{title}</span>
            <button
              onClick={toggle}
              aria-label="Collapse"
              className="text-muted-foreground hover:text-foreground text-sm px-1"
            >
              ✕
            </button>
          </div>
          <div className="overflow-y-auto p-3">{children}</div>
        </div>
      ) : (
        <button
          onClick={toggle}
          className="glass rounded-full px-3 py-2 shadow-xl flex items-center gap-2 text-xs font-semibold hover:brightness-110 transition"
        >
          {pill}
        </button>
      )}
    </div>
  );
}
