/** Film shorthand, decoded for non-filmmakers — hover tooltips everywhere the
 * abbreviations appear, so a judge reads the cinematography without prior
 * knowledge. Mirrors the backend's SHOT_VOCABULARY. */
export const FILM_TERMS: Record<string, string> = {
  ECU: "extreme close-up — eyes or a detail fill the frame",
  CU: "close-up — the face fills the frame",
  MCU: "medium close-up — chest up, emotion readable",
  MS: "medium shot — waist up, gesture visible",
  FS: "full shot — the whole body",
  LS: "long shot — figure small in the environment",
  EWS: "extreme wide establishing shot — where are we",
  POV: "point-of-view — we see what the character sees",
  OTS: "over-the-shoulder — camera behind one character, looking at the other",
  INSERT: "insert — a detail cutaway (hands, an object)",
  FG: "foreground — nearest the camera",
  MG: "midground",
  BG: "background — deepest in frame",
};

/** "MS · dolly in" → tooltip text for each recognized abbreviation. */
export function explainFilmTerm(term?: string | null): string | undefined {
  if (!term) return undefined;
  return FILM_TERMS[term.toUpperCase().trim()];
}
