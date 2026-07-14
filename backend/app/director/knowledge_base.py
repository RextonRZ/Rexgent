"""The single source of cinematic truth for the Director Engine. Plain data +
pure lookups — no I/O. Grounded by docs/superpowers/research/2026-07-15-prompt-ontology.md."""

# ── vocabulary: value -> (description, emotional function) ──
SHOT_SIZES = {
    "EWS": "extreme wide; scale and place, characters small in the world",
    "LS": "wide; whole body and its surroundings",
    "FS": "full shot; the whole body head to toe",
    "MS": "medium; waist up, neutral conversational default",
    "MCU": "medium close-up; chest up, leans into feeling",
    "CU": "close-up; the face, the primary emotional register",
    "ECU": "extreme close-up; eyes/hands/an object, maximum intensity",
    "OTS": "over-the-shoulder; two-hander geography, listener foreground",
    "POV": "point of view; what a character sees",
    "INSERT": "a detail cutaway (an object, a hand) that carries a beat",
}
CAMERA_MOVES = {
    "STATIC": "locked; a held, deliberate stillness",
    "PAN_LEFT": "pivot left; follow or reveal",
    "PAN_RIGHT": "pivot right; follow or reveal",
    "TILT_UP": "pivot up; scale, awe, a rising reveal",
    "TILT_DOWN": "pivot down; diminishment, looking away",
    "DOLLY_IN": "push in; tension, intimacy, a dawning realization",
    "DOLLY_OUT": "pull out; isolation, loss, releasing the moment",
    "HANDHELD": "unsteady; urgency, chaos (use sparingly)",
    "DRONE": "aerial; scale (exteriors only)",
}
LENSES = {
    "24mm": "wide; environment and geography, deep focus",
    "35mm": "natural wide; grounded, documentary feel",
    "50mm": "normal; how the eye sees, neutral and elegant",
    "85mm": "portrait; compressed, shallow depth, intimate",
    "135mm": "telephoto; strong compression, isolates the subject",
}
COMPOSITIONS = {
    "rule_of_thirds": "subject off-centre on a third line",
    "centered": "subject dead-centre; symmetry, formality, confrontation",
    "symmetrical": "mirrored frame; order, control, unease",
    "leading_lines": "lines draw the eye to the subject",
    "foreground_framing": "a foreground element frames the subject",
    "negative_space": "empty space around the subject; isolation",
    "over_the_shoulder": "framed past a foreground shoulder",
    "silhouette": "subject dark against a bright background",
}

# ── light QUALITY (distinct from lighting = time-of-day/mood). Model-honored terms. ──
LIGHT_QUALITIES = {
    "soft": "soft, diffused light; gentle shadows, flattering and calm",
    "hard": "hard, direct light; sharp shadows, high drama and edge",
    "side": "side light; sculpts the face, mood and volume",
    "rim": "rim light; a bright outline separating subject from background",
    "backlight": "backlight; silhouette or glow behind the subject",
    "top": "top light; downward, oppressive or clinical",
    "practical": "practical light; visible in-scene sources (lamps, neon, fire)",
}

# ── the heart: each purpose -> recommended technique ──
# duration is a (min, max) rhythm hint in seconds; dialogue = may this shot speak.
SHOT_PURPOSES = {
    "establishing": {"sizes": ["EWS", "LS"], "cameras": ["STATIC", "PAN_LEFT", "PAN_RIGHT", "DRONE"],
                     "lens": "24mm", "composition": "leading_lines", "duration": (2.0, 4.0), "dialogue": False},
    "dialogue":     {"sizes": ["MS", "MCU", "OTS"], "cameras": ["STATIC", "DOLLY_IN"],
                     "lens": "50mm", "composition": "rule_of_thirds", "duration": (3.0, 8.0), "dialogue": True},
    "reaction":     {"sizes": ["CU", "MCU", "ECU"], "cameras": ["STATIC", "DOLLY_IN"],
                     "lens": "85mm", "composition": "rule_of_thirds", "duration": (1.5, 2.5), "dialogue": False},
    "insert":       {"sizes": ["INSERT", "ECU"], "cameras": ["STATIC"],
                     "lens": "85mm", "composition": "centered", "duration": (1.0, 2.0), "dialogue": False},
    "reveal":       {"sizes": ["MS", "CU", "FS"], "cameras": ["DOLLY_IN", "PAN_LEFT", "PAN_RIGHT"],
                     "lens": "50mm", "composition": "foreground_framing", "duration": (2.0, 4.0), "dialogue": False},
    "beat":         {"sizes": ["MCU", "CU", "LS"], "cameras": ["STATIC", "DOLLY_OUT"],
                     "lens": "85mm", "composition": "negative_space", "duration": (1.5, 3.0), "dialogue": False},
    "climax":       {"sizes": ["CU", "ECU"], "cameras": ["DOLLY_IN", "HANDHELD"],
                     "lens": "85mm", "composition": "centered", "duration": (3.0, 8.0), "dialogue": True},
    "transition":   {"sizes": ["LS", "EWS", "INSERT"], "cameras": ["PAN_LEFT", "DOLLY_OUT", "STATIC"],
                     "lens": "35mm", "composition": "negative_space", "duration": (1.5, 3.0), "dialogue": False},
    "resolution":   {"sizes": ["MS", "LS", "FS"], "cameras": ["DOLLY_OUT", "STATIC"],
                     "lens": "50mm", "composition": "rule_of_thirds", "duration": (2.0, 5.0), "dialogue": True},
}

# ── genre/tone -> scene-wide look ──
GENRE_LOOKS = {
    "romance":  {"lighting": "GOLDEN_HOUR", "colour_mood": "WARM", "lens_bias": "50mm",
                 "camera_pace": "slow", "light_quality": "soft", "bgm_hint": "tender piano", "ambience_hint": "soft room tone"},
    "thriller": {"lighting": "NIGHT", "colour_mood": "COOL", "lens_bias": "85mm",
                 "camera_pace": "measured", "light_quality": "side", "bgm_hint": "sparse tension drones", "ambience_hint": "low hum, distant traffic"},
    "action":   {"lighting": "DRAMATIC_SIDE", "colour_mood": "HIGH_CONTRAST", "lens_bias": "35mm",
                 "camera_pace": "kinetic", "light_quality": "hard", "bgm_hint": "driving percussion", "ambience_hint": "wind, movement"},
    "drama":    {"lighting": "NATURAL", "colour_mood": "DESATURATED", "lens_bias": "50mm",
                 "camera_pace": "measured", "light_quality": "soft", "bgm_hint": "restrained strings", "ambience_hint": "quiet interior"},
    "horror":   {"lighting": "NIGHT", "colour_mood": "MONOCHROME", "lens_bias": "35mm",
                 "camera_pace": "slow", "light_quality": "top", "bgm_hint": "dissonant swells", "ambience_hint": "creaks, wind"},
    "comedy":   {"lighting": "NATURAL", "colour_mood": "VIVID", "lens_bias": "35mm",
                 "camera_pace": "measured", "light_quality": "soft", "bgm_hint": "light plucked strings", "ambience_hint": "bright room tone"},
    "_default": {"lighting": "NATURAL", "colour_mood": "WARM", "lens_bias": "50mm",
                 "camera_pace": "measured", "light_quality": "soft", "bgm_hint": None, "ambience_hint": None},
}

# ── show-don't-tell: emotion -> a physical/visual action the Director can stage ──
EMOTION_ACTIONS = {
    "nervous": "hands trembling, a swallowed breath",
    "angry": "jaw tightening, a step forward, fist closing",
    "afraid": "backing away, eyes widening, a hand rising",
    "grief": "eyes brimming, a slow collapse of the shoulders",
    "love": "a lingering look, fingers hesitating near the other's hand",
    "resolve": "chin lifting, shoulders squaring, a steady stare",
    "shock": "a frozen stillness, lips parting",
}

# ── incompatibilities: technique pairs that make no sense ──
_INCOMPATIBLE = {
    ("EWS", "85mm"), ("EWS", "135mm"), ("LS", "135mm"),
    ("INSERT", "24mm"), ("ECU", "24mm"),
}


def genre_look(genre: str | None) -> dict:
    return GENRE_LOOKS.get((genre or "").strip().lower(), GENRE_LOOKS["_default"])


def is_incompatible(size: str, lens: str) -> bool:
    return (size, lens) in _INCOMPATIBLE


def alt_size_for(size: str, purpose: str) -> str:
    """A different size still valid for this purpose (used to break a repeat)."""
    options = [s for s in SHOT_PURPOSES.get(purpose, {}).get("sizes", []) if s != size]
    return options[0] if options else size
