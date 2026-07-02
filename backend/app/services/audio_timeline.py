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
