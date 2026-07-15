// Every shot renders on the one video model. The allocator only picks a
// quality LEVEL — full or fast — and may defer a shot to fit the cap. Legacy
// plans persisted a "wan" tier; it now reads as full quality.
export type QualityTier = "wan" | "happyhorse" | "happyhorse_fast" | "deferred";

/** Human label for a shot's quality level. */
export function tierLabel(tier?: string | null): "Full" | "Fast" | "Deferred" {
  if (tier === "deferred") return "Deferred";
  if (tier === "happyhorse_fast") return "Fast";
  return "Full"; // "happyhorse" and legacy "wan"
}

/** True for shots that still render (not deferred). */
export function isActiveTier(tier?: string | null): boolean {
  return tier !== "deferred";
}

/** True for full-quality shots (the accent-coloured ones). */
export function isFullTier(tier?: string | null): boolean {
  return tier !== "happyhorse_fast" && tier !== "deferred";
}

/** Human label for the video MODEL a shot renders on (wan_primary routing).
 * Wan renders the visuals/continuity; HappyHorse renders the characters. This
 * is a different axis from the quality level — null when no model is known. */
export function modelLabel(model?: string | null): "Wan" | "HappyHorse" | null {
  if (model === "wan") return "Wan";
  if (model === "happyhorse") return "HappyHorse";
  return null;
}
