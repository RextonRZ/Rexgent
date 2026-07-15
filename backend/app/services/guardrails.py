import re
import json
import logging
from collections import Counter

logger = logging.getLogger(__name__)


def strip_character_names(text: str, names) -> str:
    """Remove character names — and their possessives — from free text, so a
    character whose name is also a common noun ("Bear", "Rose", "Hunter") is
    never rendered as the literal object. "Bear's apartment" -> "apartment",
    not "'s apartment"; "Rose enters" -> "enters". Whole-word, case-insensitive.

    Used anywhere a name can bleed into an image/video prompt: the location
    plate prompt, the scene setting, and the final shot prompt."""
    if not text or not names:
        return text
    result = text
    # longest name first so "Bear Junior" is consumed before "Bear"
    for name in sorted((n for n in names if n and str(n).strip()), key=len, reverse=True):
        # eat an optional trailing possessive with the name — including the
        # apostrophe-less typo the LLM writes ("Catherines face")
        result = re.sub(r"\b" + re.escape(str(name)) + r"(?:['’]?s)?\b",
                        "", result, flags=re.IGNORECASE)
    result = re.sub(r"['’]s\b", "", result)        # any orphaned possessive
    result = repair_grammar_holes(result)
    return result.strip(" ,")


def mask_offscreen_names(action: str, in_frame_names, all_cast_names) -> str:
    """Strip cast names that are NOT in this shot's frame from the action text, so
    a line like "glancing back at Anna" in a shot that doesn't include Anna cannot
    make the video model hallucinate her (a real problem on Wan, which renders the
    name literally). In-frame names are kept — the prompt compiler resolves those
    to visual descriptions. Only OFF-frame names are removed."""
    in_set = {str(n).strip() for n in (in_frame_names or []) if str(n).strip()}
    off = [n for n in (all_cast_names or [])
           if str(n).strip() and str(n).strip() not in in_set]
    return strip_character_names(action or "", off)


def repair_grammar_holes(text: str) -> str:
    """Close the wounds name-stripping leaves behind: 'photo of and Kerry'
    reads as broken; 'photo of Kerry' is what was meant."""
    result = text
    # a preposition orphaned against a conjunction: "of and X" -> "of X"
    result = re.sub(r"\b(of|with|to|for|from|between|beside|behind|near)\s+(?:and|or)\b",
                    r"\1", result, flags=re.IGNORECASE)
    # doubled conjunctions and conjunctions dangling into punctuation
    result = re.sub(r"\b(and|or)\s+\1\b", r"\1", result, flags=re.IGNORECASE)
    result = re.sub(r"\b(?:and|or)\s*([,.;])", r"\1", result, flags=re.IGNORECASE)
    result = re.sub(r"^\s*(?:and|or)\b\s*", "", result, flags=re.IGNORECASE)
    result = re.sub(r"\(\s*\)", "", result)        # empty interpolation slots
    result = re.sub(r"\s+([,.;])", r"\1", result)  # space before punctuation
    result = re.sub(r"\s{2,}", " ", result)
    return result


class PromptSanitizer:
    """Prevents text/number hallucination in generated video.

    Wan/HappyHorse render quoted text, scene numbers, and digits as garbled
    glyphs. This strips them and forces an anti-text negative prompt.
    """

    MANDATORY_NEGATIVE = (
        "text, words, letters, numbers, subtitles, watermark, logo, title card, "
        "signs, writing, captions, credits, UI, HUD, overlay, readable text, font, "
        "typography, printed, handwritten, digital display, screen text, label, "
        # multi-reference renders face-bleed: the same person must never be
        # painted onto two bodies in one frame
        "duplicate person, cloned face, identical twins, same face on two people, "
        # a character the prompt lists but does not ANCHOR sometimes gets an
        # invented arrival — rising out of the ground, popping in on a zoom
        "person materializing out of thin air, character emerging from the "
        "ground, person suddenly appearing mid-shot, extra person entering frame"
    )

    SCENE_LABEL_PATTERN = re.compile(
        r"\b(Scene|Act|INT\.|EXT\.|SCENE|ACT)\s*\d*[:\.\-]?\s*", re.IGNORECASE
    )
    # List markers at line start OR inline (", 2. ", " 3) ") — requires trailing
    # whitespace so decimals like "5.5" are never touched.
    NUMBERING_PATTERN = re.compile(r"(?:^|\s)\d+[\.\)]\s+", re.MULTILINE)
    QUOTED_TEXT_PATTERN = re.compile(r"[\"“”][^\"“”]{2,}[\"“”]")
    SINGLE_QUOTED_PATTERN = re.compile(r"['‘’][^'‘’]{2,}['‘’]")
    YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
    NUMBER_GROUP_PATTERN = re.compile(
        r"\b(\d+)\s+(people|persons|characters|figures|men|women|cops|officers|soldiers|guards)"
    )
    STANDALONE_NUMBER_PATTERN = re.compile(r"\b\d{2,}\b")
    URL_PATTERN = re.compile(r"https?://\S+")

    NUMBER_REPLACEMENTS = {
        "2": "a pair of", "3": "a small group of", "4": "a small group of",
        "5": "several", "6": "several", "7": "a group of",
        "8": "a group of", "9": "a group of", "10": "many",
    }

    def sanitize(self, prompt: str, character_names: list[str] | None = None) -> str:
        result = prompt
        result = self.QUOTED_TEXT_PATTERN.sub("", result)
        result = self.SINGLE_QUOTED_PATTERN.sub("", result)
        result = self.SCENE_LABEL_PATTERN.sub("", result)
        result = self.NUMBERING_PATTERN.sub(" ", result)
        result = self.URL_PATTERN.sub("", result)
        result = self.YEAR_PATTERN.sub("", result)

        def replace_number_group(match):
            num, noun = match.group(1), match.group(2)
            return f"{self.NUMBER_REPLACEMENTS.get(num, 'a group of')} {noun}"

        result = self.NUMBER_GROUP_PATTERN.sub(replace_number_group, result)
        result = self.STANDALONE_NUMBER_PATTERN.sub("", result)

        if character_names:
            # strip names AND their possessives ("Bear's" -> "", not "'s")
            result = strip_character_names(result, character_names)

        result = re.sub(r"\s{2,}", " ", result).strip()
        result = re.sub(r",\s*,", ",", result)
        result = result.strip(", ")
        return result

    def get_mandatory_negative_prompt(self) -> str:
        return self.MANDATORY_NEGATIVE

    def inject_negative_prompt(self, existing_negative: str = "") -> str:
        if existing_negative:
            return f"{existing_negative}, {self.MANDATORY_NEGATIVE}"
        return self.MANDATORY_NEGATIVE


class JsonOutputValidator:
    """Hardening for Qwen-Max JSON responses."""

    def clean_and_parse(self, raw: str):
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        cleaned = re.sub(r",\s*}", "}", cleaned)
        cleaned = re.sub(r",\s*]", "]", cleaned)
        return json.loads(cleaned)

    def is_truncated(self, raw: str) -> bool:
        cleaned = raw.strip()
        open_braces = cleaned.count("{") - cleaned.count("}")
        open_brackets = cleaned.count("[") - cleaned.count("]")
        return open_braces > 0 or open_brackets > 0

    def detect_prompt_leakage(self, response: str, system_prompt: str, min_match_len: int = 30) -> bool:
        rl, pl = response.lower(), system_prompt.lower()
        for i in range(max(0, len(pl) - min_match_len)):
            if pl[i:i + min_match_len] in rl:
                logger.warning("Prompt leakage detected in model response")
                return True
        return False

    def detect_repetition(self, data, threshold: int = 3) -> bool:
        values = self._extract_strings(data)
        counts = Counter(v for v in values if len(v) > 10)
        for value, count in counts.items():
            if count >= threshold:
                logger.warning(f"Repetition detected: '{value[:40]}...' x{count}")
                return True
        return False

    def _extract_strings(self, obj, results=None) -> list[str]:
        if results is None:
            results = []
        if isinstance(obj, str):
            results.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                self._extract_strings(v, results)
        elif isinstance(obj, list):
            for item in obj:
                self._extract_strings(item, results)
        return results


class CostCircuitBreaker:
    def __init__(self, budget: float = 40.0, reserve_pct: float = 0.15,
                 shot_cap: float = 2.0, max_retries: int = 15):
        self.budget = budget
        self.ceiling = budget * (1 - reserve_pct)
        self.shot_cap = shot_cap
        self.max_retries = max_retries

    def should_stop(self, current_cost: float) -> bool:
        return current_cost >= self.ceiling

    def exceeds_shot_cap(self, estimated_cost: float) -> bool:
        return estimated_cost > self.shot_cap

    def retries_exhausted(self, total_retries: int) -> bool:
        return total_retries > self.max_retries

    def remaining(self, current_cost: float) -> float:
        return max(0.0, self.ceiling - current_cost)


class InputSanitizer:
    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(previous|above|all)\s+(instructions|prompts|rules)", re.IGNORECASE),
        re.compile(r"disregard\s+(previous|above|all|everything)", re.IGNORECASE),
        re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
        re.compile(r"\b(SYSTEM|ASSISTANT|USER)\s*:", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\b", re.IGNORECASE),
        re.compile(r"act\s+as\s+(if\s+you\s+are|a)\b", re.IGNORECASE),
        re.compile(r"pretend\s+to\s+be\b", re.IGNORECASE),
        re.compile(r"from\s+now\s+on\s+you\b", re.IGNORECASE),
    ]

    def sanitize(self, text: str, max_length: int = 1000) -> str:
        result = text
        for pattern in self.INJECTION_PATTERNS:
            m = pattern.search(result)
            if m:
                logger.warning(f"Prompt injection stripped: '{m.group()}'")
                result = pattern.sub("", result)
        result = result.strip()
        if len(result) > max_length:
            result = result[:max_length]
        return result


_FOOTWEAR = re.compile(r"\b(sneakers?|shoes?|boots?|heels|loafers|slippers|sandals)\b",
                       re.IGNORECASE)
_BAREFOOT = re.compile(r"\bbare\s*foot(ed)?\b|\bbare\s+feet\b", re.IGNORECASE)
_NUMERIC_DURATION = re.compile(r"\b\d+\s*seconds?\b", re.IGNORECASE)
# a duration whose digit the number-stripper ate: "Duration: seconds." or a
# dangling "seconds." with no number in front of it
_ORPHAN_DURATION = re.compile(
    r"\bDuration:?\s*seconds\.?|(?<![0-9])(?<![0-9]\s)\bseconds\b\.?",
    re.IGNORECASE)


def validate_and_repair_prompt(prompt: str, duration=None) -> tuple[str, list[str]]:
    """The last gate before a prompt reaches a video model: repair what can
    be repaired and NAME every repair, so corruption is loud, never silent.
    Checks: replacement characters, empty/broken interpolation holes, missing
    numeric duration, and wardrobe self-contradictions (a prompt saying both
    'sneakers' and 'bare feet' — the bible's wardrobe wins)."""
    repairs: list[str] = []
    p = prompt or ""
    if "�" in p:
        p = p.replace("�", " ")
        repairs.append("removed replacement characters")
    healed = repair_grammar_holes(p)
    if healed != p:
        repairs.append("closed broken interpolation holes")
        p = healed
    if _FOOTWEAR.search(p) and _BAREFOOT.search(p):
        p = _BAREFOOT.sub("feet", p)
        repairs.append("wardrobe contradiction: dropped the barefoot mention, the bible's footwear wins")
    if duration is not None:
        orphaned = _ORPHAN_DURATION.sub("", p)
        if orphaned != p:
            p = orphaned
        if not _NUMERIC_DURATION.search(p):
            p = p.rstrip().rstrip(",") + f" Duration: {int(duration)} seconds."
            repairs.append("restored numeric duration")
    p = re.sub(r"\s{2,}", " ", p).strip()
    return p, repairs


_NAME_QUALIFIER = re.compile(r"\s*\([^)]*\)\s*$")


def canonical_character(name: str, known) -> str:
    """'KERRY (ON SCREEN)' means KERRY, and 'EIRIK' means 'Eirik Halden'.
    The storyboard LLM appends stage qualifiers and drops surnames despite
    instructions, and every exact-match consumer (validator, reference
    stacks, continuity) must resolve the variant back to the cast member it
    refers to. A bare first name resolves only when it is UNAMBIGUOUS — two
    cast members sharing it leave the name unchanged rather than guess.
    Unknown names come back unchanged."""
    n = (name or "").strip()
    if not n:
        return n
    known_map = {str(k).strip().upper(): str(k) for k in known}
    if n.upper() in known_map:
        return known_map[n.upper()]
    base = _NAME_QUALIFIER.sub("", n).strip()
    if base and base.upper() in known_map:
        return known_map[base.upper()]
    # unique first-name match: shots often write just 'EIRIK' for
    # 'Eirik Halden' — resolve when exactly one cast member's first
    # token is that name (qualifier-stripped variant included)
    probe = (base or n).upper()
    firsts = [full for key, full in known_map.items()
              if key.split() and key.split()[0] == probe]
    if len(firsts) == 1:
        return firsts[0]
    return n


def filter_to_cast(names, cast_names) -> list:
    """Canonicalize each name against the cast and keep ONLY real cast members,
    deduped, order preserved. Extras (background people, animals, one-time
    figures) must never enter characters_in_frame: they have no plate to lock,
    so the router and the reference stack would chase an identity that cannot
    exist — or the preflight would refuse the whole job. An extra stays in the
    action text and renders as a generic figure."""
    cast = [str(n) for n in (cast_names or []) if str(n).strip()]
    cast_upper = {n.upper() for n in cast}
    out: list = []
    for n in (names or []):
        c = canonical_character(str(n), cast)
        if str(c).upper() in cast_upper and c not in out:
            out.append(c)
    return out


_NAME_ARTICLES = {"the", "a", "an"}
_NAME_POSSESSIVES = {"their", "theirs", "his", "her", "hers", "my", "mine",
                     "your", "yours", "our", "ours", "its"}
_NAME_MODIFIERS = {
    "old", "young", "elderly", "middle-aged", "aged", "tall", "short", "big",
    "small", "little", "lone", "certain", "mysterious", "unknown", "unidentified",
    "unnamed", "nameless", "strange", "shadowy", "hooded", "masked", "random",
    "another", "other", "same", "first", "second", "third", "fourth", "fifth",
    "next", "last", "main", "background", "generic", "various", "several",
}
# Words that are NEVER a real given name — a "character" whose name reduces to
# only these is a placeholder / extra, not cast. Deliberately EXCLUDES words that
# are also common first names (Rose, Hunter, Grace, Faith, Hope, Joy, Angel,
# Dawn, May, June, Sky, Mercy) so a real character is never dropped.
_GENERIC_PERSON_NOUNS = {
    "man", "men", "woman", "women", "boy", "boys", "girl", "girls", "child",
    "children", "kid", "kids", "baby", "infant", "guy", "guys", "lady", "ladies",
    "gentleman", "gentlemen", "person", "persons", "figure", "figures",
    "silhouette", "stranger", "strangers", "someone", "somebody", "people",
    "crowd", "crowds", "group", "mob", "pair", "couple", "everyone", "anyone",
    "nobody", "individual", "human",
    # relations
    "brother", "sister", "mother", "father", "son", "daughter", "parent",
    "parents", "sibling", "husband", "wife", "spouse", "cousin", "aunt", "uncle",
    "grandmother", "grandfather", "grandma", "grandpa", "granny", "mom", "mum",
    "dad", "papa", "mama", "neighbour", "neighbor", "friend", "boss", "colleague",
    "twin", "twins", "widow", "widower", "orphan",
    # one-off roles / extras / titles (a proper name alongside keeps it: 'Doctor
    # Kim' survives, 'Doctor' alone does not)
    "guard", "guards", "nurse", "officer", "officers", "cop", "cops", "policeman",
    "policewoman", "police", "waiter", "waitress", "bartender", "driver",
    "soldier", "soldiers", "narrator", "announcer", "receptionist", "clerk",
    "vendor", "passerby", "onlooker", "bystander", "patron", "customer",
    "beggar", "guest", "guests", "host", "victim", "witness", "suspect",
    "attacker", "assailant", "employee", "worker", "workers", "staff", "voice",
    "villager", "villagers", "townsperson", "townsfolk", "maid", "butler",
    "cook", "farmer", "fisherman", "shopkeeper", "servant", "guardian",
    "presence", "intruder", "assistant", "detective", "captain", "sergeant",
    "inspector", "agent", "general", "colonel", "major", "lieutenant", "doctor",
    "professor", "chief", "judge", "mayor", "king", "queen", "prince", "princess",
    "priest", "monk", "nun", "reverend", "coach", "teacher", "student",
    "manager", "waitperson", "crew", "figurehead",
    # occupations that turn up as UNNAMED figures (a proper name alongside keeps
    # them: 'Reporter Kim' survives, 'Reporter' does not). Deliberately excludes
    # occupation words that double as real names/surnames — Baker, Mason, Cooper,
    # Carter, Hunter, Fisher, Smith, Archer, Knight, Page — so those survive.
    "reporter", "journalist", "photographer", "cameraman", "pilot", "chef",
    "lawyer", "attorney", "banker", "engineer", "thief", "thieves", "robber",
    "burglar", "dancer", "singer", "actor", "actress", "sculptor", "musician",
    "sailor", "secretary", "bodyguard", "salesman", "saleswoman", "cashier",
    "mechanic", "plumber", "electrician", "carpenter", "janitor", "cleaner",
    "chauffeur", "bouncer", "gambler", "boxer", "referee", "umpire", "pastor",
    "sheriff", "deputy", "spy", "hacker", "assassin", "mercenary", "warden",
    "jailer", "executioner", "prosecutor", "editor", "poet", "comedian",
    "magician", "clown", "stewardess", "conductor", "tourist", "prisoner",
    "inmate", "patient", "dentist", "surgeon", "therapist", "scientist",
    "principal", "librarian", "accountant", "broker", "operator", "technician",
    "laborer", "labourer", "foreman", "miner", "rancher", "cowboy", "warrior",
    "sentry", "scout", "messenger", "courier", "postman", "mailman", "trucker",
    "cabbie", "admiral", "commander", "medic", "gangster", "mobster", "crook",
}
_UNKNOWN_TOKENS = {"unknown", "unnamed", "unidentified", "n/a", "na", "tbd",
                   "tba", "none", "null", "nil", "placeholder", "character",
                   "unspecified", "anon", "anonymous"}


def is_placeholder_character_name(name) -> bool:
    """True when a 'character' name is a generic placeholder that must NEVER be
    cast: an unknown/unnamed marker ('UNKNOWN FIGURE'), a bare common noun
    ('Man', 'Woman'), an article/adjective + generic noun ('the old man', 'a
    mysterious figure'), a numbered extra ('Guard 2'), or a relational/role
    label ('their brother', 'the mother', 'Guard'). A name SURVIVES when, after
    dropping articles, possessives, adjectives and numbers, at least one token
    remains that is a proper name (not in the generic-noun set) — so 'Detective
    Halloran' and 'Doctor Kim' are kept, 'Detective' and 'the guard' are not.
    Words that are legitimately common first names are excluded from the generic
    set, so a real character is never dropped."""
    n = str(name or "").strip()
    if not n:
        return True
    low = n.lower()
    # whole-string unknown marker ('n/a', 'tbd') or no letters at all ('???')
    if low in _UNKNOWN_TOKENS or not re.search(r"[a-z]", low):
        return True
    tokens = [t for t in re.split(r"[\s\-_/#().,]+", low) if t]
    if not tokens:
        return True
    if any(t in _UNKNOWN_TOKENS for t in tokens):
        return True
    meaningful = [t for t in tokens
                  if t not in _NAME_ARTICLES and t not in _NAME_POSSESSIVES
                  and t not in _NAME_MODIFIERS and not t.isdigit()]
    if not meaningful:
        return True
    return all(t in _GENERIC_PERSON_NOUNS for t in meaningful)


class PreGenerationValidator:
    def validate(self, characters: list[dict], shots: list[dict]) -> dict:
        issues: list[str] = []
        missing_visuals: list[str] = []
        warnings: list[str] = []

        if not shots:
            return {"pass": False, "issues": ["No shots in storyboard"], "missing_visuals": [],
                    "warnings": [], "total_shots": 0, "total_duration": 0}

        names_in_shots = set()
        for shot in shots:
            for name in (shot.get("characters_in_frame") or []):
                names_in_shots.add(name)

        char_map = {c["name"]: c for c in characters}
        for name in names_in_shots:
            c = char_map.get(canonical_character(name, char_map.keys()))
            if not c:
                # a non-cast name is an EXTRA that leaked into characters_in_frame:
                # it has no plate by design, so a missing plate must WARN, never
                # block the whole job — the shot still renders, the figure is
                # simply not identity-locked.
                warnings.append(f"{name}: not in the cast — renders as an extra "
                                "with no identity lock")
            elif not c.get("video_prompt_fragment") and not c.get("visual_description"):
                missing_visuals.append(f"{name}: no visual description")

        if missing_visuals:
            issues.append(f"{len(missing_visuals)} character(s) missing visual descriptions")

        total_duration = sum(s.get("estimated_duration_seconds", 0) for s in shots)
        if total_duration <= 0:
            issues.append("Total estimated duration is 0")

        return {
            "pass": len(issues) == 0,
            "issues": issues,
            "missing_visuals": missing_visuals,
            "warnings": warnings,
            "total_shots": len(shots),
            "total_duration": total_duration,
        }
