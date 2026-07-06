"""Context compression: pass compact digests, not the full script JSON.

Non-creative agents (wardrobe planning, clarification) only read scene-level
facts — who is in the scene, where, and what it is about. Sending them the
whole structured script (every dialogue line and stage direction) burns
prompt tokens linearly with script length. The digest keeps exactly the
fields those agents use and drops the rest, typically cutting the prompt by
well over half on a multi-scene script.
"""


def script_digest(structured: dict | None) -> dict:
    s = structured or {}
    scenes = []
    for sc in s.get("scenes", []):
        scenes.append({
            "scene_number": sc.get("scene_number"),
            "heading": sc.get("heading"),
            "location": sc.get("location"),
            "time_of_day": sc.get("time_of_day"),
            "characters_present": sc.get("characters_present", []),
            "emotional_beat": sc.get("emotional_beat"),
            "summary": sc.get("summary"),
        })
    return {
        "logline": s.get("logline"),
        "characters_mentioned": s.get("characters_mentioned", []),
        "scenes": scenes,
    }
