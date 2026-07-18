"""Deterministic character/style trait detection: which cast members are
non-human creatures, and whether the drama's look is stylized (cartoon,
anime, pixel art). Both drive graceful degradation — ArcFace embeddings and
the human plate standard (standing, head to shoes, arms at sides) only make
sense for photoreal humans; a rabbit or a cel-shaded face gets a natural
full-body reference and skips face verification instead of failing it."""
import re

# species nouns that mark a NON-HUMAN cast member when they appear in the
# character's own description (never the name: a man nicknamed Bear is a man)
_SPECIES = (
    "rabbit|bunny|cat|kitten|dog|puppy|bear|bird|owl|eagle|parrot|fox|wolf|"
    "lion|tiger|mouse|rat|hamster|horse|pony|donkey|cow|goat|sheep|pig|"
    "panda|penguin|duck|chicken|rooster|frog|turtle|snake|lizard|dragon|"
    "monkey|gorilla|elephant|giraffe|deer|squirrel|hedgehog|otter|seal|"
    "dolphin|whale|shark|fish|octopus|crab|spider|bee|butterfly|"
    "robot|android|alien|monster|creature|ghost|fairy|goblin|elf|troll"
)
# "cat-like reflexes" describes a person, not a cat: the bare noun only,
# never a hyphenated adjective
_SPECIES_RE = re.compile(rf"\b({_SPECIES})s?\b(?!-)", re.I)

_STYLIZED_RE = re.compile(
    r"\b(cartoon|anime|manga|toon|cel[ -]?shaded|2d|3[ -]?d|cgi|pixel|8[ -]?bit|"
    r"16[ -]?bit|claymation|stop[ -]?motion|comic|illustrated|illustration|"
    r"hand[ -]?drawn|watercolor|watercolour|sketch|low[ -]?poly|voxel|chibi|"
    r"ghibli|pixar|disney)\b", re.I)


def species_of(*texts) -> str | None:
    """The first creature noun found across the given texts, or None for a
    human (or empty) description."""
    for t in texts:
        if not t:
            continue
        m = _SPECIES_RE.search(str(t))
        if m:
            return m.group(1).lower()
    return None


def is_creature(char) -> bool:
    """Whether this cast member is a non-human creature, read from their own
    DESCRIPTIONS (never the name — a man nicknamed Bear stays a man)."""
    return species_of(getattr(char, "physical_description", None),
                      getattr(char, "visual_description", None),
                      getattr(char, "role", None)) is not None


def is_stylized_style(*texts) -> bool:
    """Whether the drama's look is non-photoreal (cartoon, anime, pixel...).
    ArcFace embeddings are junk on stylized faces, so face verification is
    skipped rather than failed when this is true."""
    return any(t and _STYLIZED_RE.search(str(t)) for t in texts)
