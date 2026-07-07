/** Plain-words setting labels from screenplay headings.
 *
 * "INT./EXT." is screenwriter jargon most users don't know — the UI shows
 * "Indoor"/"Outdoor" chips instead. The label is re-derived from the location
 * wording (not just the stored prefix), so scripts saved before the backend
 * INT/EXT fix still display correctly: a street tagged "INT." reads Outdoor.
 */

const PREFIX_RE =
  /^\s*(INT\.?\s*\/\s*EXT\.?|EXT\.?\s*\/\s*INT\.?|INT\.?|EXT\.?|内景|外景)[\s.\-–—]*/i;

// outdoor compounds first: 屋顶 (rooftop) must win over the indoor 屋 it contains
const OUTDOOR = [
  "屋顶", "天台", "街道", "街头", "大街", "街", "小巷", "巷", "马路", "公路",
  "路口", "桥", "广场", "公园", "花园", "庭院", "院子", "森林", "树林", "海滩",
  "海边", "沙漠", "田野", "码头", "港口", "户外", "郊外", "野外", "废墟",
  "城墙", "集市", "夜市", "门口", "门外", "山", "河", "湖",
  "street", "alley", "road", "bridge", "square", "plaza", "park", "garden",
  "courtyard", "rooftop", "roof", "mountain", "forest", "woods", "river",
  "lake", "beach", "desert", "field", "dock", "harbor", "outside", "outdoors",
  "ruins", "market", "gate",
];
const INDOOR = [
  "屋", "房", "室", "厅", "堂", "店", "馆", "公寓", "家中", "厨房", "卧室",
  "书房", "地下室", "仓库", "办公", "教室", "医院", "酒吧", "餐厅", "旅馆",
  "酒店", "牢房", "车厢", "船舱", "殿", "庙",
  "room", "hut", "cabin", "house", "apartment", "office", "hall", "shop",
  "store", "bar", "restaurant", "kitchen", "bedroom", "basement", "warehouse",
  "hospital", "classroom", "hotel", "cell", "temple", "palace", "interior",
  "inside", "tavern", "inn",
];

function matches(text: string, word: string): boolean {
  if (/[a-z]/.test(word)) return new RegExp(`\\b${word}\\b`).test(text);
  return text.includes(word);
}

export interface ParsedHeading {
  /** plain-words chip, null when the wording gives no signal */
  setting: "Indoor" | "Outdoor" | null;
  /** heading with the INT./EXT. jargon stripped for display */
  text: string;
}

export function parseSceneHeading(
  heading?: string | null,
  location?: string | null
): ParsedHeading {
  const raw = (heading || "").trim();
  const text = raw.replace(PREFIX_RE, "").replace(/^[\s\-–—]+/, "").trim() || raw;
  const probe = `${location || ""} ${raw}`.replace(PREFIX_RE, "").toLowerCase();

  let setting: ParsedHeading["setting"] = null;
  if (OUTDOOR.some((w) => matches(probe, w))) setting = "Outdoor";
  else if (INDOOR.some((w) => matches(probe, w))) setting = "Indoor";
  else {
    // no wording signal: trust the stored prefix
    const m = raw.match(PREFIX_RE);
    const tag = m?.[1]?.toUpperCase().replace(/\s/g, "") ?? "";
    if (tag.startsWith("INT") && !tag.includes("EXT")) setting = "Indoor";
    else if (tag.startsWith("EXT") && !tag.includes("INT")) setting = "Outdoor";
    else if (tag === "内景") setting = "Indoor";
    else if (tag === "外景") setting = "Outdoor";
  }
  return { setting, text };
}
