// The visual style catalog behind the create-drama style picker. Values are
// the backend style_catalog keys; "photoreal" is local only (the backend
// stores NULL and keeps the classic cinematic look).
export interface VisualStyleDef {
  value: string;
  label: string;
}

export const PHOTOREAL = "photoreal";

/** Per style family, a quiet card accent within the house design system: the
 * chip labels the look, the bar tints the card's top hairline. Photoreal (and
 * unknown styles) return null and keep the plain house card. */
export function styleAccent(
  style?: string | null
): { label: string; chip: string; bar: string } | null {
  const s = (style ?? "").toLowerCase();
  if (!s || s === PHOTOREAL) return null;
  const label = VISUAL_STYLES.find((v) => v.value === s)?.label ?? s;
  if (["anime", "manga", "chibi"].includes(s))
    return { label, chip: "bg-pink-500/15 text-pink-300", bar: "bg-pink-400/50" };
  if (["ghibli", "watercolor", "illustrated", "hand-drawn", "sketch"].includes(s))
    return { label, chip: "bg-emerald-500/15 text-emerald-300", bar: "bg-emerald-400/50" };
  if (["pixel", "8-bit", "16-bit", "voxel", "low-poly"].includes(s))
    return { label, chip: "bg-amber-500/15 text-amber-300", bar: "bg-amber-400/50" };
  if (["claymation", "stop-motion"].includes(s))
    return { label, chip: "bg-orange-500/15 text-orange-300", bar: "bg-orange-400/50" };
  // pixar, disney, cartoon, cel-shaded, 2d, comic and friends
  return { label, chip: "bg-sky-500/15 text-sky-300", bar: "bg-sky-400/50" };
}

export const VISUAL_STYLES: VisualStyleDef[] = [
  { value: PHOTOREAL, label: "Photoreal cinematic" },
  { value: "pixar", label: "Pixar style 3D" },
  { value: "disney", label: "Disney style" },
  { value: "ghibli", label: "Ghibli style" },
  { value: "anime", label: "Anime" },
  { value: "chibi", label: "Chibi" },
  { value: "manga", label: "Manga" },
  { value: "cartoon", label: "Cartoon" },
  { value: "cel-shaded", label: "Cel shaded" },
  { value: "2d", label: "Flat 2D" },
  { value: "comic", label: "Comic book" },
  { value: "illustrated", label: "Illustrated storybook" },
  { value: "hand-drawn", label: "Hand drawn" },
  { value: "watercolor", label: "Watercolor" },
  { value: "sketch", label: "Sketch" },
  { value: "claymation", label: "Claymation" },
  { value: "stop-motion", label: "Stop motion" },
  { value: "pixel", label: "Pixel art" },
  { value: "8-bit", label: "8 bit retro" },
  { value: "16-bit", label: "16 bit retro" },
  { value: "low-poly", label: "Low poly 3D" },
  { value: "voxel", label: "Voxel" },
];
