from app.services.wardrobe_planner import map_variant_for_scene


def build_reference_stack(characters_in_frame, scene_number, bible,
                          prev_last_frame_url, model_cap):
    """Priority: characters -> last-frame chain (continuity) -> location -> style.
    Trim from the bottom to model_cap. The continuity frame sits right after the
    character identity plates so a tight model_cap can't drop the shot-to-shot link.
    Returns a list of {"type": "reference_image", "url": ...} dicts."""
    ordered = []
    for name in characters_in_frame:
        ch = bible["characters"].get(name)
        if not ch:
            continue
        variant = map_variant_for_scene(ch.get("variants", []), scene_number)
        if variant and variant.get("plate_image_url"):
            ordered.append(variant["plate_image_url"])
    if prev_last_frame_url:
        ordered.append(prev_last_frame_url)
    loc = (bible.get("location_by_scene") or {}).get(scene_number)
    if loc:
        ordered.append(loc)
    if bible.get("style_plate"):
        ordered.append(bible["style_plate"])
    ordered = ordered[:model_cap]
    return [{"type": "reference_image", "url": u} for u in ordered]
