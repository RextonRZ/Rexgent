// The visual style catalog behind the create-drama style picker. Values are
// the backend style_catalog keys; "photoreal" is local only (the backend
// stores NULL and keeps the classic cinematic look).
export interface VisualStyleDef {
  value: string;
  label: string;
}

export const PHOTOREAL = "photoreal";

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
