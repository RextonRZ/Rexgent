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

/** The same vocabulary in Chinese, shown when the shot's own text is Chinese
 * so a zh drama's storyboard reads in one language. Standard zh film terms. */
export const FILM_TERMS_ZH: Record<string, { name: string; hint: string }> = {
  ECU: { name: "大特写", hint: "眼睛或细节充满画面" },
  CU: { name: "特写", hint: "面部充满画面" },
  MCU: { name: "中近景", hint: "胸部以上，情绪清晰可读" },
  MS: { name: "中景", hint: "腰部以上，动作可见" },
  FS: { name: "全景", hint: "全身入画" },
  WS: { name: "大全景", hint: "整个空间尽收眼底" },
  LS: { name: "远景", hint: "人物在环境中显得很小" },
  EWS: { name: "大远景", hint: "交代故事发生的地点" },
  POV: { name: "主观镜头", hint: "观众看到角色所看到的" },
  OTS: { name: "过肩镜头", hint: "镜头越过一人肩膀拍摄另一人" },
  INSERT: { name: "插入镜头", hint: "手部或物件等细节的切入画面" },
  FG: { name: "前景", hint: "离镜头最近的一层" },
  MG: { name: "中间层", hint: "画面的中间层次" },
  BG: { name: "背景", hint: "画面最深处" },
};

/** Camera moves in Chinese; unknown moves fall back to the English shape. */
const CAMERA_MOVES_ZH: Record<string, string> = {
  STATIC: "固定",
  DOLLY_IN: "推镜",
  DOLLY_OUT: "拉镜",
  PAN_LEFT: "左摇",
  PAN_RIGHT: "右摇",
  TILT_UP: "上摇",
  TILT_DOWN: "下摇",
  HANDHELD: "手持",
  DRONE: "航拍",
  ZOOM_IN: "变焦推近",
  ZOOM_OUT: "变焦拉远",
  TRACKING: "跟拍",
};

/** Whether the text carries Chinese prose — the per-shot signal that its
 * card chrome should render in Chinese too. */
export function hasCJK(text?: string | null): boolean {
  return /[一-鿿]/.test(text ?? "");
}

/** "MS" -> "Medium Shot (MS)" (or "中景 (MS)"). Unrecognized terms come back
 * as given. */
export function fullShotType(term?: string | null, zh = false): string | undefined {
  if (!term) return undefined;
  const key = term.toUpperCase().trim();
  const t = (zh ? FILM_TERMS_ZH[key] : undefined) ?? FILM_TERMS[key];
  return t ? `${t.name} (${key})` : term;
}

/** The hover hint for a recognized abbreviation. */
export function explainFilmTerm(term?: string | null, zh = false): string | undefined {
  if (!term) return undefined;
  const key = (term ?? "").toUpperCase().trim();
  return ((zh ? FILM_TERMS_ZH[key] : undefined) ?? FILM_TERMS[key])?.hint;
}

/** "DOLLY_IN" -> "dolly in" (or "推镜" for zh shots). */
export function cameraMoveLabel(move?: string | null, zh = false): string | undefined {
  if (!move) return undefined;
  const key = move.toUpperCase().trim();
  if (zh && CAMERA_MOVES_ZH[key]) return CAMERA_MOVES_ZH[key];
  return move.toLowerCase().replace(/_/g, " ");
}
