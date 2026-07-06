from app.services.wardrobe_planner import map_variant_for_scene

# Framings wide enough that the room genuinely fills the frame. On tighter
# shots the subject dominates and the background is mostly soft focus, so
# anchoring the whole wide location plate there just forces the model to
# reproduce the entire sharp room behind a close-up — the "flat zoom backdrop"
# artifact. Those shots lean on the last-frame chain for room continuity.
WIDE_FRAMINGS = {"MS", "FS", "LS", "EWS", "WS"}


def build_reference_stack(characters_in_frame, scene_number, bible,
                          prev_last_frame_url, model_cap, shot_type=None):
    """Per character: identity (default) face plate FIRST to lock the face, then the
    scene's costume plate for the outfit. Then last-frame chain (continuity) ->
    location (wide shots only) -> style. Dedupe and trim to model_cap.

    Anchoring the identity plate in EVERY scene keeps the face consistent even when
    the outfit — and its separately-generated plate — changes between scenes; without
    it, a drifted costume plate makes the character look like a different person.
    Returns a list of {"type": "reference_image", "url": ...} dicts."""
    ordered = []
    for name in characters_in_frame:
        ch = bible["characters"].get(name)
        if not ch:
            continue
        variants = ch.get("variants", [])
        identity = next((v.get("plate_image_url") for v in variants
                         if v.get("is_default") and v.get("plate_image_url")), None)
        if identity:
            ordered.append(identity)
        scene_variant = map_variant_for_scene(variants, scene_number)
        if scene_variant and scene_variant.get("plate_image_url"):
            ordered.append(scene_variant["plate_image_url"])
    if prev_last_frame_url:
        ordered.append(prev_last_frame_url)
    # location plate only on wide framings (or when the shot type is unknown)
    include_location = shot_type is None or str(shot_type).upper() in WIDE_FRAMINGS
    loc = (bible.get("location_by_scene") or {}).get(scene_number)
    if loc and include_location:
        ordered.append(loc)
    if bible.get("style_plate"):
        ordered.append(bible["style_plate"])
    # dedupe preserving order (identity == scene plate for default-outfit scenes)
    seen, deduped = set(), []
    for u in ordered:
        if u and u not in seen:
            seen.add(u)
            deduped.append(u)
    return [{"type": "reference_image", "url": u} for u in deduped[:model_cap]]
