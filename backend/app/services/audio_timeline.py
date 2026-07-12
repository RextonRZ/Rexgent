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
    individual shot is tagged as speaking. With repeated scene groups the
    FIRST appearance anchors the scene."""
    offs: dict[int, float] = {}
    t = 0.0
    for scene in scene_plan:
        if scene["scene_number"] not in offs:
            offs[scene["scene_number"]] = round(t, 3)
        t += sum(float(s.get("duration") or 0.0) for s in scene.get("shots", []))
    return offs


def dialogue_shot_offsets(scene_plan: list[dict]) -> dict[int, list[float]]:
    """Global start (seconds) of each dialogue-bearing shot, per scene.
    scene_plan: ordered [{scene_number, shots: [{duration, has_dialogue}]}].
    A scene may appear in several non-contiguous groups (a cut re-ordered in
    the editor) — its starts MERGE instead of the last group winning."""
    offs: dict[int, list[float]] = {}
    t = 0.0
    for scene in scene_plan:
        starts = offs.setdefault(scene["scene_number"], [])
        for shot in scene.get("shots", []):
            if shot.get("has_dialogue"):
                # the line starts where the clip's own mouth starts moving
                # (VAD onset of its fake speech), not at the hard cut
                starts.append(round(t + float(shot.get("speech_onset") or 0.0), 3))
            t += float(shot.get("duration") or 0.0)
    return offs


# the voice may stretch or compress to match the on-screen mouth, but only
# within what still sounds human: beyond these bounds a partial match wins
TEMPO_MIN, TEMPO_MAX = 0.75, 1.3


def dialogue_shot_mouths(scene_plan: list[dict]) -> dict[int, list]:
    """Per scene, each dialogue-bearing shot's measured MOUTH duration (how
    long its fake speech ran, from ASR sentence spans) — parallel to
    dialogue_shot_offsets. None where unmeasured."""
    mouths: dict[int, list] = {}
    for scene in scene_plan:
        lst = mouths.setdefault(scene["scene_number"], [])
        for shot in scene.get("shots", []):
            if shot.get("has_dialogue"):
                lst.append(shot.get("mouth_dur"))
    return mouths


def line_tempo(line_duration: float, mouth_duration) -> float | None:
    """atempo factor that plays the line across the mouth's real speaking
    span. tempo < 1 stretches, > 1 compresses; clamped to stay natural, and
    tiny mismatches are left alone."""
    if not mouth_duration or mouth_duration <= 0.5 or line_duration <= 0:
        return None
    tempo = max(TEMPO_MIN, min(TEMPO_MAX, line_duration / float(mouth_duration)))
    if abs(tempo - 1.0) < 0.08:
        return None
    return round(tempo, 3)


def place_dialogue(line_rows: list[dict], scene_plan: list[dict], gap: float = 0.2) -> list[dict]:
    """Align each scene's dialogue lines to the shots that actually speak them:
    line k of a scene starts when that scene's k-th dialogue-bearing shot starts,
    so the voice lands on the matching picture instead of drifting.
    line_rows: [{scene_number, line_index, audio_path, duration}]. Order-based —
    no fragile text matching. Extra lines (a shot folded two) continue back-to-back."""
    offs = dialogue_shot_offsets(scene_plan)
    mouths = dialogue_shot_mouths(scene_plan)
    scene_offs = scene_global_offsets(scene_plan)
    by_scene: dict = {}
    for r in sorted(line_rows, key=lambda x: (x["scene_number"], x["line_index"])):
        by_scene.setdefault(r["scene_number"], []).append(r)

    out = []
    seen: set = set()
    for scene in scene_plan:
        n = scene["scene_number"]
        # a scene split across several cut groups is placed ONCE, on its
        # merged offsets — not re-placed per group
        if n in seen:
            continue
        seen.add(n)
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
            raw_dur = float(ln.get("duration") or 0.0)
            played_dur = raw_dur
            seg = {"audio_path": ln["audio_path"], "start": round(start, 3)}
            # match the voice's pace to the on-screen mouth: if the clip's
            # fake speech ran 3.5s and the TTS line is 2.0s, stretch the line
            # (pitch-preserving atempo downstream) so lips and voice end together
            scene_mouths = mouths.get(n, [])
            mouth = scene_mouths[i] if i < len(scene_mouths) else None
            tempo = line_tempo(raw_dur, mouth)
            if tempo:
                seg["tempo"] = tempo
                played_dur = raw_dur / tempo
            seg["duration"] = round(played_dur, 3)
            # text/character ride along so burned captions share the exact
            # timing of the voice they subtitle
            if ln.get("text"):
                seg["text"] = ln["text"]
            if ln.get("character"):
                seg["character"] = ln["character"]
            out.append(seg)
            prev_end = start + played_dur + gap

    # ── the GLOBAL no-overlap sweep: the per-scene guard above resets at
    # scene boundaries, so a scene whose dialogue overflows its own footage
    # used to bleed into the next scene's first line. Sort every placed line
    # by absolute start and push any collision forward — two voices can never
    # overlap anywhere in the episode, scene boundary or not. ──
    out.sort(key=lambda s: s["start"])
    prev_end = None
    for seg in out:
        if prev_end is not None and seg["start"] < prev_end:
            seg["start"] = round(prev_end, 3)
        prev_end = seg["start"] + float(seg.get("duration") or 0.0) + gap
    return out
