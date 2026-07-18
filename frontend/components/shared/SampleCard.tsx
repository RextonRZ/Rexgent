"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

/** A thumbnail pick card for the genre and visual style strips: sample image,
 * label overlaid on a bottom gradient, ring when selected, plain labeled tile
 * when the image is missing. Used by the New drama modal and the Script page. */
export function SampleCard({
  active,
  onClick,
  img,
  label,
}: {
  active: boolean;
  onClick: () => void;
  img: string;
  label: string;
}) {
  const [broken, setBroken] = useState(false);
  const ref = useRef<HTMLButtonElement>(null);
  // center the current pick when the strip mounts, so the selection is
  // never hiding off the edge of the row
  useEffect(() => {
    if (active)
      ref.current?.scrollIntoView({ block: "nearest", inline: "center" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <button
      ref={ref}
      type="button"
      onClick={onClick}
      className={cn(
        "relative aspect-video w-28 shrink-0 snap-start overflow-hidden rounded-lg border text-left transition-all",
        active
          ? "border-primary ring-1 ring-primary"
          : "border-border opacity-80 hover:opacity-100 hover:border-primary/40"
      )}
    >
      {!broken && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={img}
          alt={label}
          loading="lazy"
          onError={() => setBroken(true)}
          className="absolute inset-0 h-full w-full object-cover"
        />
      )}
      {broken && <span className="absolute inset-0 bg-white/[0.04]" />}
      <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent px-1.5 pb-1 pt-3">
        <span className="block truncate text-[10px] font-medium text-white">
          {label}
        </span>
      </span>
      {active && (
        <span className="absolute right-1 top-1 rounded-full bg-primary px-1.5 text-[9px] font-semibold text-primary-foreground">
          ✓
        </span>
      )}
    </button>
  );
}
