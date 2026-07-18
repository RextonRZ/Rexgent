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

# The Chinese matcher. A zh run writes physical_description in Chinese ("一只白
# 色的小狗"), which has no ASCII word boundaries and none of the English nouns
# above — so a pet like 雪球 was mis-cast as a human. CJK needs no \b, so these
# match as plain substrings; longest/most-specific first (熊猫 panda beats 猫
# cat). 宠物 (pet) is a catch-all for a species the model didn't name.
# High-collision single chars are DROPPED for their compounds only: 象 lives in
# 象征 (symbolize), 马 in 马上 (at once), 虎 in 马虎 (careless), 牛 in 牛仔
# (cowboy) — so elephant/horse/tiger/cow match only as 大象/小马/老虎/奶牛.
_SPECIES_ZH_RE = re.compile(
    "熊猫|猫头鹰|长颈鹿|大猩猩|仓鼠|松鼠|老鼠|袋鼠|刺猬|海豚|海豹|鲨鱼|章鱼|"
    "螃蟹|蜘蛛|蜜蜂|蝴蝶|青蛙|乌龟|蜥蜴|鹦鹉|企鹅|公鸡|狐狸|狮子|老虎|恐龙|"
    "兔子|小马|马驹|骏马|斑马|奶牛|水牛|小牛|山羊|绵羊|大象|小象|机器人|机械人|"
    "外星人|怪兽|怪物|幽灵|精灵|妖精|巨魔|猴子|宠物|"
    "兔|猫|狗|熊|鸟|鹰|狼|猪|鸭|鹅|鸡|鹿|羊|蛇|龟|蛙|鱼|龙|猴|鬼|鼠")

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
        s = str(t)
        m = _SPECIES_RE.search(s)
        if m:
            return m.group(1).lower()
        m = _SPECIES_ZH_RE.search(s)
        if m:
            return m.group(0)
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
