"""INT./EXT. correction for scene headings.

The structurer LLM regularly mislabels settings — a street tagged INT., or
the same location flipping between INT and EXT across scenes (scene 1
"INT. street", scene 4 "EXT. street"). Deterministic post-processing:

1. infer interior/exterior from the location wording (Chinese + English);
2. force the SAME location to carry the SAME prefix in every scene;
3. rebuild the heading with the corrected prefix and expose the machine
   answer as scene["setting_type"] so UIs can label it in plain words.
"""
import re

# Order matters: outdoor compounds are checked before the indoor words they
# contain (屋顶 rooftop must win over the generic indoor 屋).
OUTDOOR_WORDS = [
    "屋顶", "天台", "街道", "街头", "大街", "街", "小巷", "巷", "马路", "公路",
    "路口", "桥", "广场", "公园", "花园", "庭院", "院子", "山", "森林", "树林",
    "河", "湖", "海滩", "海边", "沙漠", "田野", "码头", "港口", "户外", "郊外",
    "野外", "废墟", "城墙", "市集", "集市", "夜市", "门口", "门外",
    "street", "alley", "road", "highway", "bridge", "square", "plaza", "park",
    "garden", "courtyard", "rooftop", "roof", "mountain", "forest", "woods",
    "river", "lake", "beach", "desert", "field", "dock", "harbor", "outside",
    "outdoors", "ruins", "market", "gate",
]
INDOOR_WORDS = [
    "屋", "房", "室", "厅", "堂", "店", "馆", "局", "公寓", "家中", "厨房",
    "卧室", "书房", "地下室", "仓库", "办公", "教室", "医院", "酒吧", "餐厅",
    "旅馆", "酒店", "牢房", "车厢", "船舱", "殿", "庙",
    "room", "hut", "cabin", "house", "apartment", "flat", "office", "hall",
    "shop", "store", "bar", "restaurant", "kitchen", "bedroom", "basement",
    "warehouse", "hospital", "classroom", "hotel", "cell", "temple", "palace",
    "interior", "inside", "tavern", "inn",
]

PREFIX_RE = re.compile(
    r"^\s*(INT\.?\s*/\s*EXT\.?|EXT\.?\s*/\s*INT\.?|INT\.?|EXT\.?|内景|外景)[\s.\-–—]*",
    re.IGNORECASE,
)


def _matches(text: str, word: str) -> bool:
    # ASCII words need boundaries ("car" must not hit "scar"); CJK has no
    # word boundaries, plain containment is correct there.
    if re.search(r"[a-z]", word):
        return re.search(rf"\b{re.escape(word)}\b", text) is not None
    return word in text


def infer_setting(text: str) -> str | None:
    """"interior" / "exterior" from location wording; None when unclear."""
    t = PREFIX_RE.sub("", (text or "")).lower()
    for w in OUTDOOR_WORDS:
        if _matches(t, w):
            return "exterior"
    for w in INDOOR_WORDS:
        if _matches(t, w):
            return "interior"
    return None


def _kind_from_prefix(heading: str) -> str | None:
    m = PREFIX_RE.match(heading or "")
    if not m:
        return None
    tag = m.group(1).upper().replace(" ", "")
    if tag.startswith("INT") and "EXT" not in tag:
        return "interior"
    if tag.startswith("EXT") and "INT" not in tag:
        return "exterior"
    if tag == "内景":
        return "interior"
    if tag == "外景":
        return "exterior"
    return None


def normalize_scene_headings(structured: dict) -> dict:
    """Fix INT/EXT in place across a structured script. Never fatal, never
    drops content — a scene the keywords can't classify keeps the LLM's call."""
    scenes = structured.get("scenes") or []
    if not scenes:
        return structured

    # pass 1: what the wording says, per scene
    worded: dict[int, str | None] = {}
    for i, sc in enumerate(scenes):
        worded[i] = infer_setting(f"{sc.get('location') or ''} {sc.get('heading') or ''}")

    # pass 2: one verdict per location — keyword majority, else prefix majority
    by_loc: dict[str, list[int]] = {}
    for i, sc in enumerate(scenes):
        key = (sc.get("location") or "").strip().lower()
        by_loc.setdefault(key or f"__solo_{i}", []).append(i)

    for indices in by_loc.values():
        votes = [worded[i] for i in indices if worded[i]]
        if not votes:
            votes = [k for i in indices
                     if (k := _kind_from_prefix(scenes[i].get("heading") or ""))]
        kind = max(set(votes), key=votes.count) if votes else None
        for i in indices:
            sc = scenes[i]
            final = kind or _kind_from_prefix(sc.get("heading") or "")
            if final is None:
                continue
            prefix = "INT." if final == "interior" else "EXT."
            rest = PREFIX_RE.sub("", (sc.get("heading") or "").strip()).strip(" -–—")
            if not rest:
                parts = [p for p in [sc.get("location"), sc.get("time_of_day")] if p]
                rest = " - ".join(str(p) for p in parts)
            sc["heading"] = f"{prefix} {rest}".strip()
            sc["setting_type"] = final
    return structured
