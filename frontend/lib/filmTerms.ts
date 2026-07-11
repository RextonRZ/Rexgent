/** Film shorthand, decoded for non-filmmakers. One source of truth: every
 * abbreviation maps to its full name (shown as the primary label) and a plain
 * hint (shown on hover). Mirrors the backend's SHOT_VOCABULARY. */
export const FILM_TERMS: Record<string, { name: string; hint: string }> = {
  ECU: { name: "Extreme Close-Up", hint: "eyes or a detail fill the frame" },
  CU: { name: "Close-Up", hint: "the face fills the frame" },
  MCU: { name: "Medium Close-Up", hint: "chest up, emotion readable" },
  MS: { name: "Medium Shot", hint: "waist up, gesture visible" },
  FS: { name: "Full Shot", hint: "the whole body in frame" },
  WS: { name: "Wide Shot", hint: "the whole space in view" },
  LS: { name: "Long Shot", hint: "figure small in the environment" },
  EWS: { name: "Extreme Wide Shot", hint: "establishing where we are" },
  POV: { name: "Point of View", hint: "we see what the character sees" },
  OTS: {
    name: "Over the Shoulder",
    hint: "camera behind one character, looking at the other",
  },
  INSERT: { name: "Insert", hint: "a detail cutaway such as hands or an object" },
  FG: { name: "Foreground", hint: "nearest the camera" },
  MG: { name: "Midground", hint: "the middle plane" },
  BG: { name: "Background", hint: "deepest in frame" },
};

/** "MS" -> "Medium Shot (MS)". Unrecognized terms come back as given. */
export function fullShotType(term?: string | null): string | undefined {
  if (!term) return undefined;
  const key = term.toUpperCase().trim();
  const t = FILM_TERMS[key];
  return t ? `${t.name} (${key})` : term;
}

/** The hover hint for a recognized abbreviation. */
export function explainFilmTerm(term?: string | null): string | undefined {
  if (!term) return undefined;
  return FILM_TERMS[term.toUpperCase().trim()]?.hint;
}
