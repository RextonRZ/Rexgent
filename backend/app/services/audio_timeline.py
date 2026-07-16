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
# within what still sounds human. Slowing a line DRAGS it, so the floor is
# tight (~15% max): past that the quiet native bed covers the trailing mouth
# movement instead of stretching the words into a sluggish read.
TEMPO_MIN, TEMPO_MAX = 0.85, 1.3
# A rendered mouth can babble far longer than the real line (hallucinated
# speech past the words). Never chase a mouth more than this multiple of the
# line's natural length: beyond it the bed covers the gap, so the voice is
# neither dragged (atempo) nor over-paused chasing lips that aren't speaking.
MOUTH_FILL_CAP = 1.5


def _effective_mouth(line_duration: float, mouth_duration) -> float | None:
    """The mouth span we actually try to fill: the measured span, capped so a
    hallucinated over-long mouth can't drag or over-pace the voice. None when
    the mouth is unmeasured or too short to trust."""
    if not mouth_duration or mouth_duration <= 0.5 or line_duration <= 0:
        return None
    return round(min(float(mouth_duration), line_duration * MOUTH_FILL_CAP), 3)


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


def paced_text(text: str, level: int) -> str:
    """Rewrite a line with `level` written pauses (ellipses) at even word
    boundaries: 'I can't do this anymore.' -> 'I... can't do this... anymore.'
    TTS honors the punctuation, so the take comes back naturally longer —
    a slower PERFORMANCE, where atempo past ~15% only makes a dragged one.
    Captions keep the original text; only the audio is re-performed."""
    words = [w for w in (text or "").split() if w]
    if level <= 0 or len(words) < 2:
        return text
    n = min(level, len(words) - 1)
    marks = set()
    for k in range(1, n + 1):
        m = round(k * len(words) / (n + 1))
        marks.add(min(max(m, 1), len(words) - 1))
    out = []
    for i, w in enumerate(words, start=1):
        if i in marks and not w.endswith(("...", "…")):
            w = w.rstrip(".,;:") + "..."
        out.append(w)
    return " ".join(out)


def pacing_retakes(line_rows: list[dict], scene_plan: list[dict]) -> list[tuple]:
    """Lines whose voice is SO much shorter than the on-screen mouth that the
    tempo clamp cannot bridge the gap — the mouth would keep moving after the
    line ends. Pairs lines to shots exactly like place_dialogue (k-th line ↔
    k-th speaking shot). Returns [(line_row, mouth_duration)]."""
    mouths = dialogue_shot_mouths(scene_plan)
    by_scene: dict = {}
    for r in sorted(line_rows, key=lambda x: (x["scene_number"], x["line_index"])):
        by_scene.setdefault(r["scene_number"], []).append(r)
    out = []
    for n, lines in by_scene.items():
        scene_mouths = mouths.get(n, [])
        for i, ln in enumerate(lines):
            mouth = scene_mouths[i] if i < len(scene_mouths) else None
            dur = float(ln.get("duration") or ln.get("duration_seconds") or 0.0)
            m = _effective_mouth(dur, mouth)
            if m is None or dur <= 0:
                continue
            # chase the CAPPED mouth: a hallucinated over-long mouth is bridged
            # only up to the cap, the rest is left to the bed
            if dur / m < TEMPO_MIN - 0.02:
                out.append((ln, m))
    return out


def line_tempo(line_duration: float, mouth_duration) -> float | None:
    """atempo factor that plays the line across the mouth's real speaking
    span. tempo < 1 stretches, > 1 compresses; clamped to stay natural (never
    dragging a line more than ~15%), and tiny mismatches are left alone. The
    mouth is capped first so a hallucinated over-long mouth can't drag it."""
    mouth = _effective_mouth(line_duration, mouth_duration)
    if mouth is None:
        return None
    tempo = max(TEMPO_MIN, min(TEMPO_MAX, line_duration / mouth))
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
