"""Turn a drama's genre + emotional beats into a music MOOD (a registry music
category), so the export can auto-suggest a fitting track. Heuristic + documented;
a future Music Agent can replace this with a smarter mapping."""
from app.assets.registry import categories_for

_GENRE_TO_MOOD = {
    "romance": "romance", "drama": "sadness", "comedy": "comedy",
    "action": "action", "thriller": "thriller", "horror": "horror",
    "fantasy": "fantasy", "historical": "historical", "sci-fi": "fantasy",
    "mystery": "thriller", "inspirational": "inspirational",
}
_BEAT_KEYWORDS = {
    "sadness": ("heartbreak", "breakup", "grief", "tearful", "goodbye", "loss", "death"),
    "thriller": ("tension", "suspense", "chase", "danger"),
    "happy": ("joy", "celebration", "wedding", "reunion"),
    "romance": ("love", "confession", "kiss", "longing"),
    "action": ("fight", "battle"),
}
_MUSIC_MOODS = set(categories_for("music"))


def derive_mood(genre=None, beats=None) -> str:
    """Pick a music mood. Genre first (if it maps), else scan beats for keywords,
    else 'daily'."""
    g = (genre or "").strip().lower()
    if g in _GENRE_TO_MOOD and _GENRE_TO_MOOD[g] in _MUSIC_MOODS:
        return _GENRE_TO_MOOD[g]
    text = " ".join(beats or []).lower()
    for mood, kws in _BEAT_KEYWORDS.items():
        if mood in _MUSIC_MOODS and any(k in text for k in kws):
            return mood
    return "daily"
