from app.services.wardrobe_planner import map_variant_for_scene

# Framings wide enough that the room genuinely fills the frame. On tighter
# shots the subject dominates and the background is mostly soft focus, so
# anchoring the whole wide location plate there just forces the model to
# reproduce the entire sharp room behind a close-up — the "flat zoom backdrop"
# artifact. Those shots lean on the last-frame chain for room continuity.
WIDE_FRAMINGS = {"MS", "FS", "LS", "EWS", "WS"}

# Framings that still SHOW the room even though they aren't wide: an
# over-the-shoulder, POV or MCU frames a subject against real visible space,
# and rendering one without the location plate lets the model reinvent the
# set (measured: OTS shots scored background 0.30, and an MCU scene-opener
# invented a whole different cabin at bg 0.30). These get the location
# anchor too; WIDE_FRAMINGS stays strict because it also picks the
# scene-anchor source frame. Only CU/ECU stay exempt — there the face fills
# the frame and a sharp room reference reads as a flat backdrop.
ROOM_FRAMINGS = WIDE_FRAMINGS | {"OTS", "POV", "MCU"}


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
        # ONE plate per character: the scene's costume variant already carries the
        # FACE (image-edited FROM the identity plate) AND the correct outfit.
        # Sending a SECOND identity plate — in the character's DEFAULT (different)
        # outfit — handed HappyHorse two conflicting references of the same person
        # in different clothes; asked to take "face from image 1, outfit from image
        # 2" it blended them and the face drifted. A foreground occluder (face
        # unseen) is the same single plate, framed as a back/shoulder.
        scene_variant = map_variant_for_scene(variants, scene_number)
        plate = ((scene_variant or {}).get("plate_image_url")
                 or next((v.get("plate_image_url") for v in variants
                          if v.get("is_default") and v.get("plate_image_url")), None))
        if plate:
            entries.append((plate, "costume" if name in fg else "character", name))
    # prev_frame is NOT attached: that frame CONTAINS the cast in-picture, and
    # sent as a reference image beside the identity plates it renders as an
    # EXTRA COPY of the characters (two Deok-hyuns in one shot). Frame
    # continuity belongs ONLY to Wan's typed first_frame / first_clip
    # continuation. scene_anchor DOES ride — but the runner only ever assigns
    # it from a PEOPLE-FREE shot's closing frame (the establishing/atmosphere
    # clip), so it anchors the room without carrying anyone who could double.
    _ = prev_last_frame_url
    if scene_anchor_url:
        entries.append((scene_anchor_url, "scene_anchor", None))
    # location plate on any framing that shows the room (or when unknown)
    include_location = ((shot_type is None or str(shot_type).upper() in ROOM_FRAMINGS)
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


def image_ref_legend(provenance) -> str:
    """A one-line map from [Image N] to what each reference image IS, so the
    model ties each person to their own plate instead of guessing which face
    goes where. N is 1-based and matches the media order sent to the model
    (the same order as build_reference_stack_labeled's provenance)."""
    role_label = {
        "character": "{c} (their face AND the exact outfit to wear)",
        "identity": "{c}'s face",
        "costume": "{c}'s outfit",
        "prev_frame": "the previous shot's frame for continuity",
        # the room references show the PLACE, not the camera view: without the
        # angle clause the model pastes the image as a flat backdrop and every
        # shot shows the same props from the same side regardless of the
        # planned camera position
        "scene_anchor": ("the scene's set - keep its furniture and props, "
                         "rendered from THIS shot's camera angle"),
        "location": ("the location and set - keep its furniture and props, "
                     "rendered from THIS shot's camera angle"),
        "style": "the visual style",
    }
    parts = []
    has_person = False
    for i, p in enumerate(provenance or [], start=1):
        if p.get("role") in ("character", "identity", "costume"):
            has_person = True
        tmpl = role_label.get(p.get("role"), "a reference")
        parts.append(f"[Image {i}] is " + tmpl.format(c=p.get("character") or "the subject"))
    if not parts:
        return ""
    # a scenery shot references only location/style/frame — DON'T mention people
    # or the model invents them into an empty landscape; the person-matching guide
    # applies only when a real face/outfit plate is in the stack.
    preamble = (
        "Reference image guide (match each person to their OWN image, never "
        "swap faces or outfits between people): " if has_person
        else "Reference images (match the location and visual style only, no people): "
    )
    return preamble + "; ".join(parts) + "."


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
