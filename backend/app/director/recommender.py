from app.director import knowledge_base as kb
from app.director.types import LookProfile


def recommend_look(genre: str | None, tone: str | None = None) -> LookProfile:
    """Scene-wide look from genre (tone reserved for future refinement). Never
    raises: an unknown genre returns the neutral default."""
    spec = kb.genre_look(genre)
    return LookProfile(
        lighting=spec["lighting"], colour_mood=spec["colour_mood"],
        lens_bias=spec["lens_bias"], camera_pace=spec["camera_pace"],
        light_quality=spec.get("light_quality", "soft"),
        bgm_hint=spec.get("bgm_hint"), ambience_hint=spec.get("ambience_hint"),
    )
