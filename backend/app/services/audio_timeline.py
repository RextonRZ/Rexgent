def scene_offsets(scene_numbers: list[int], shot_durations: dict[int, list[float]]) -> dict[int, float]:
    """Global timeline offset (seconds) of each scene = sum of prior scenes' shot durations."""
    offs, running = {}, 0.0
    for n in scene_numbers:
        offs[n] = running
        running += sum(shot_durations.get(n, []))
    return offs


def assemble_scene_segment(lines: list[dict], scene_offset: float, gap: float = 0.2) -> list[dict]:
    """Place a scene's lines back-to-back from scene_offset. lines: [{audio_path, duration}]."""
    out, t = [], scene_offset
    for ln in lines:
        out.append({"audio_path": ln["audio_path"], "start": round(t, 3)})
        t += float(ln.get("duration", 0.0)) + gap
    return out


def scene_global_offsets(scene_plan: list[dict]) -> dict[int, float]:
    """Global start (seconds) of each scene = sum of all prior scenes' shot
    durations. This is the reliable anchor for a scene's dialogue even when no
    individual shot is tagged as speaking."""
    offs: dict[int, float] = {}
    t = 0.0
    for scene in scene_plan:
        offs[scene["scene_number"]] = round(t, 3)
        t += sum(float(s.get("duration") or 0.0) for s in scene.get("shots", []))
    return offs


def dialogue_shot_offsets(scene_plan: list[dict]) -> dict[int, list[float]]:
    """Global start (seconds) of each dialogue-bearing shot, per scene.
    scene_plan: ordered [{scene_number, shots: [{duration, has_dialogue}]}]."""
    offs: dict[int, list[float]] = {}
    t = 0.0
    for scene in scene_plan:
        starts = []
        for shot in scene.get("shots", []):
            if shot.get("has_dialogue"):
                starts.append(round(t, 3))
            t += float(shot.get("duration") or 0.0)
        offs[scene["scene_number"]] = starts
    return offs


def place_dialogue(line_rows: list[dict], scene_plan: list[dict], gap: float = 0.2) -> list[dict]:
    """Align each scene's dialogue lines to the shots that actually speak them:
    line k of a scene starts when that scene's k-th dialogue-bearing shot starts,
    so the voice lands on the matching picture instead of drifting.
    line_rows: [{scene_number, line_index, audio_path, duration}]. Order-based —
    no fragile text matching. Extra lines (a shot folded two) continue back-to-back."""
    offs = dialogue_shot_offsets(scene_plan)
    scene_offs = scene_global_offsets(scene_plan)
    by_scene: dict = {}
    for r in sorted(line_rows, key=lambda x: (x["scene_number"], x["line_index"])):
        by_scene.setdefault(r["scene_number"], []).append(r)

    out = []
    for scene in scene_plan:
        n = scene["scene_number"]
        lines = by_scene.get(n, [])
        starts = offs.get(n, [])
        # never fall back to 0.0: if no shot in this scene is tagged as
        # speaking, anchor the scene's lines at the scene's own global offset
        # so scenes play in sequence instead of piling onto the front.
        scene_start = scene_offs.get(n, 0.0)
        prev_end = None
        for i, ln in enumerate(lines):
            if i < len(starts):
                start = starts[i]
            elif prev_end is not None:
                start = prev_end
            else:
                start = starts[0] if starts else scene_start
            # never overlap the previous line: when a line's audio outruns its
            # shot (a two-person exchange in short shots), the next line waits
            # for it to finish instead of talking over it.
            if prev_end is not None and start < prev_end:
                start = prev_end
            seg = {"audio_path": ln["audio_path"], "start": round(start, 3),
                   "duration": round(float(ln.get("duration") or 0.0), 3)}
            # text/character ride along so burned captions share the exact
            # timing of the voice they subtitle
            if ln.get("text"):
                seg["text"] = ln["text"]
            if ln.get("character"):
                seg["character"] = ln["character"]
            out.append(seg)
            prev_end = start + float(ln.get("duration") or 0.0) + gap
    return out
