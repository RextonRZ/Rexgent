"""Predict the model each shot will render on, matching the runtime routing, so
the storyboard label can never drift from what actually renders. Pure — no I/O."""
from app.services.shot_roles import classify_shot_role, angle_changed


def _chars(shot):
    return [str(c) for c in (getattr(shot, "characters_in_frame", None) or [])]


def _castable(bible, name):
    """A real cast member the runner can face-lock. Membership in the bible is
    the test, NOT a plate URL: plates are painted by casting AFTER boarding,
    and by the time the shot actually renders they exist. Requiring the plate
    here made every entrance in the review window (boarded, not yet cast) read
    as a Wan continuation on the storyboard badge."""
    return str(name) in (bible.get("characters") or {})


def predict_scene_plan(shots, bible, *, identity_routing_v2, anchor_ref_model,
                       lipsync_enabled,
                       happyhorse_native_talk=False,
                       route_continuation_to_happyhorse=False,
                       wan_primary=False,
                       multishot_enabled=False,
                       multishot_max_shots=0):
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
            c not in _chars(prev) and c not in fg and _castable(bible, c)
            for c in _chars(shot))
        chg = angle_changed(getattr(prev, "shot_type", None) if prev else None,
                            getattr(shot, "shot_type", None),
                            bool((getattr(shot, "blocking_json", None) or {}).get("reverse_angle")))
        role = classify_shot_role(has_frame_anchor=has_anchor,
                                  has_locked_newcomer=bool(newcomer), is_angle_change=chg)
        ref_native = role in ("anchor", "entrance", "continue_reangle")
        model = "happyhorse" if (ref_native and anchor_ref_model == "happyhorse") else "wan"
        # continuation shots render on HappyHorse r2v (not wan i2v) when opted in
        # — mirrors _dispatch_by_role's continue_hold routing under the flag.
        if route_continuation_to_happyhorse and role == "continue_hold":
            model = "happyhorse"
        has_dialogue = bool((getattr(shot, "dialogue", None) or "").strip())
        # Wan-primary OVERRIDES the model to mirror _dispatch_by_role's wan_primary
        # branch: HappyHorse renders the CHARACTERS (a shot that speaks, locks a
        # newcomer, is an establishing anchor with faces, or is a REANGLE — angle
        # changes never ride continuation); Wan renders every other silent
        # visual. OFF -> the routing above is left untouched.
        if wan_primary:
            has_faces = bool(_chars(shot))
            model = ("happyhorse"
                     if (has_dialogue or bool(newcomer)
                         or (role == "continue_reangle" and has_faces)
                         or (role == "anchor" and has_faces))
                     else "wan")
        # native talk makes HappyHorse SPEAK the line itself; the badge follows
        # the model that ACTUALLY renders (any HappyHorse-routed dialogue shot
        # talks — mirrors the runner's to_happyhorse gate). A Wan visual or a
        # wan-r2v anchor cannot speak, so it never badges.
        talk = happyhorse_native_talk and has_dialogue and model == "happyhorse"
        lipsync = lipsync_enabled and talk
        out.append({"model": model, "lipsync": bool(lipsync)})
        prev = shot
    # Multishot beats OVERRIDE the per-shot routing: the runner groups the
    # scene with the SAME group_beats call and renders every >=2-shot beat as
    # ONE wan multi-shot clip (_process_beat), so those shots' badges must say
    # Wan no matter what the role routing above picked. A wan beat never
    # speaks, so lipsync drops with it.
    if multishot_enabled and multishot_max_shots >= 2:
        from app.services.multishot import group_beats
        idx = 0
        for unit in group_beats(list(shots), multishot_max_shots,
                                wan_primary=wan_primary):
            if len(unit) >= 2:
                for k in range(idx, idx + len(unit)):
                    out[k] = {"model": "wan", "lipsync": False}
            idx += len(unit)
    return out
