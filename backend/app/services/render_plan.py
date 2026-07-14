"""Predict the model each shot will render on, matching the runtime routing, so
the storyboard label can never drift from what actually renders. Pure — no I/O."""
from app.services.shot_roles import classify_shot_role, angle_changed


def _chars(shot):
    return [str(c) for c in (getattr(shot, "characters_in_frame", None) or [])]


def _has_plate(bible, name):
    return any(v.get("plate_image_url")
               for v in (bible.get("characters", {}).get(name) or {}).get("variants", []))


def predict_scene_plan(shots, bible, *, identity_routing_v2, anchor_ref_model,
                       anchor_lipsync, lipsync_enabled, wan_on_same_cast=False):
    """Per-shot {model, lipsync} for one scene's ordered shots. Mirrors runtime routing."""
    out = []
    prev = None
    for shot in shots:
        if not identity_routing_v2:
            model = "wan" if (getattr(shot, "quality_tier", None) == "wan") else "happyhorse"
            out.append({"model": model, "lipsync": False})
            prev = shot
            continue
        fg = {str(c) for c in (getattr(shot, "foreground_characters", None) or [])}
        has_anchor = prev is not None
        newcomer = has_anchor and any(
            c not in _chars(prev) and c not in fg and _has_plate(bible, c)
            for c in _chars(shot))
        chg = angle_changed(getattr(prev, "shot_type", None) if prev else None,
                            getattr(shot, "shot_type", None),
                            bool((getattr(shot, "blocking_json", None) or {}).get("reverse_angle")))
        role = classify_shot_role(has_frame_anchor=has_anchor,
                                  has_locked_newcomer=bool(newcomer), is_angle_change=chg)
        # same-cast reangle routes to wan continuation when opted in (mirrors runtime)
        if role == "continue_reangle" and wan_on_same_cast:
            role = "continue_hold"
        ref_native = role in ("anchor", "entrance", "continue_reangle")
        model = "happyhorse" if (ref_native and anchor_ref_model == "happyhorse") else "wan"
        visible = [c for c in _chars(shot) if c not in fg]
        single = bool((getattr(shot, "dialogue", None) or "").strip()) and len(visible) == 1
        lipsync = (lipsync_enabled and single
                   and (role == "continue_hold" or (ref_native and anchor_lipsync)))
        out.append({"model": model, "lipsync": bool(lipsync)})
        prev = shot
    return out
