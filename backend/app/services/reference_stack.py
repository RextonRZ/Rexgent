from app.services.wardrobe_planner import map_variant_for_scene

# Framings wide enough that the room genuinely fills the frame. On tighter
# shots the subject dominates and the background is mostly soft focus, so
# anchoring the whole wide location plate there just forces the model to
# reproduce the entire sharp room behind a close-up — the "flat zoom backdrop"
# artifact. Those shots lean on the last-frame chain for room continuity.
WIDE_FRAMINGS = {"MS", "FS", "LS", "EWS", "WS"}


def build_reference_stack_labeled(characters_in_frame, scene_number, bible,
                                  prev_last_frame_url, model_cap, shot_type=None,
                                  scene_anchor_url=None, suppress_location=False,
                                  foreground_characters=None):
    """Same stack as build_reference_stack, but each reference keeps its role
    (identity | costume | prev_frame | scene_anchor | location | style) and,
    where relevant, the character it belongs to. The provenance list is
    persisted per clip so cross-shot reuse of the bible is provable, not asserted.

    scene_anchor_url is the last frame of the scene's first wide shot: unlike
    the prev-frame chain it survives a run of close-ups (whose frames carry no
    background), so the room's set dressing doesn't get reinvented mid-scene.
    suppress_location drops the location plate once the scene's set STATE has
    changed (a broken vase must not be re-anchored to its pristine plate).

    Returns (media, provenance): media is the API payload, provenance the
    matching [{"url", "role", "character"?}] records in the same order."""
    fg = set(foreground_characters or [])
    entries: list[tuple[str, str, str | None]] = []
    # Subjects (face-visible) first so a tight model_cap never trims their face
    # lock in favour of a foreground occluder. A foreground character keeps only
    # their costume plate (outfit continuity for the back/shoulder) — NOT the
    # identity plate, whose face lock would drag them front-and-centre in a shot
    # that is really about someone else.
    ordered = ([n for n in characters_in_frame if n not in fg]
               + [n for n in characters_in_frame if n in fg])
    for name in ordered:
        ch = bible["characters"].get(name)
        if not ch:
            continue
        variants = ch.get("variants", [])
        identity = next((v.get("plate_image_url") for v in variants
                         if v.get("is_default") and v.get("plate_image_url")), None)
        if identity and name not in fg:
            entries.append((identity, "identity", name))
        scene_variant = map_variant_for_scene(variants, scene_number)
        if scene_variant and scene_variant.get("plate_image_url"):
            entries.append((scene_variant["plate_image_url"], "costume", name))
    if prev_last_frame_url:
        entries.append((prev_last_frame_url, "prev_frame", None))
    if scene_anchor_url:
        entries.append((scene_anchor_url, "scene_anchor", None))
    # location plate only on wide framings (or when the shot type is unknown)
    include_location = ((shot_type is None or str(shot_type).upper() in WIDE_FRAMINGS)
                        and not suppress_location)
    loc = (bible.get("location_by_scene") or {}).get(scene_number)
    if loc and include_location:
        entries.append((loc, "location", None))
    if bible.get("style_plate"):
        entries.append((bible["style_plate"], "style", None))
    # dedupe preserving order (identity == scene plate for default-outfit scenes)
    seen: set = set()
    deduped: list[tuple[str, str, str | None]] = []
    for url, role, character in entries:
        if url and url not in seen:
            seen.add(url)
            deduped.append((url, role, character))
    deduped = deduped[:model_cap]
    media = [{"type": "reference_image", "url": u} for u, _, _ in deduped]
    provenance = [{"url": u, "role": r, **({"character": c} if c else {})}
                  for u, r, c in deduped]
    return media, provenance


def build_reference_stack(characters_in_frame, scene_number, bible,
                          prev_last_frame_url, model_cap, shot_type=None,
                          foreground_characters=None):
    """Per character: identity (default) face plate FIRST to lock the face, then the
    scene's costume plate for the outfit. Then last-frame chain (continuity) ->
    location (wide shots only) -> style. Dedupe and trim to model_cap.

    Anchoring the identity plate in EVERY scene keeps the face consistent even when
    the outfit — and its separately-generated plate — changes between scenes; without
    it, a drifted costume plate makes the character look like a different person.
    Returns a list of {"type": "reference_image", "url": ...} dicts."""
    media, _ = build_reference_stack_labeled(
        characters_in_frame, scene_number, bible,
        prev_last_frame_url, model_cap, shot_type,
        foreground_characters=foreground_characters)
    return media
