"""Fit each speaking shot's render duration to its real dialogue audio.

The video models render fixed duration tiers (5s or 10s). A 5s shot holding a
7s line forces the next line to wait past its own picture — the overlap /
drift the user hears in two-person conversations. So BEFORE video generation
we synthesize the dialogue, measure each line, and size every speaking shot
to the smallest tier that fits its lines.

Lines map to shots with the SAME rule the export mixer uses (the scene's k-th
dialogue line lands on its k-th speaking shot, extras fold onto the last one),
so the picture a voice is fitted to is the picture it plays over.
"""
import uuid

# duration tiers the wan / happyhorse APIs accept
ALLOWED_DURATIONS = (5, 10)
GAP = 0.3  # breathing room after each line


def fit_shot_durations(scene_plan: list[dict], lines: list[dict]) -> dict:
    """Pure fitting logic. scene_plan: ordered
    [{scene_number, shots: [{id, duration, has_dialogue}]}];
    lines: [{scene_number, line_index, duration}].
    Returns {shot_id: fitted_seconds} for shots whose duration should change."""
    by_scene: dict = {}
    for r in sorted(lines, key=lambda x: (x["scene_number"], x["line_index"])):
        by_scene.setdefault(r["scene_number"], []).append(float(r.get("duration") or 0.0))
    changes: dict = {}
    for scene in scene_plan:
        durs = by_scene.get(scene["scene_number"], [])
        speaking = [s for s in scene.get("shots", []) if s.get("has_dialogue")]
        if not speaking or not durs:
            continue
        # k-th line -> k-th speaking shot; extra lines fold onto the last one
        need = [0.0] * len(speaking)
        for k, d in enumerate(durs):
            need[min(k, len(speaking) - 1)] += d + GAP
        for shot, needed in zip(speaking, need):
            fitted = next((t for t in ALLOWED_DURATIONS if t >= needed),
                          ALLOWED_DURATIONS[-1])
            if fitted != shot.get("duration"):
                changes[shot["id"]] = fitted
    return changes


def fit_project_shot_durations(db, project_id: str) -> int:
    """Apply the fit to a project's shots from its synthesized LineAudio.
    Returns how many shots changed. No-op when there is no dialogue audio yet."""
    from app.models.script import Script, Scene
    from app.models.shot import Shot
    from app.models.line_audio import LineAudio

    pid = uuid.UUID(str(project_id))
    rows = db.query(LineAudio).filter(LineAudio.project_id == pid).all()
    if not rows:
        return 0
    script = (db.query(Script).filter(Script.project_id == pid)
              .order_by(Script.created_at.desc()).first())
    if not script:
        return 0
    scenes = db.query(Scene).filter(Scene.script_id == script.id).order_by(Scene.number).all()
    shot_by_id: dict = {}
    scene_plan = []
    for s in scenes:
        shots = db.query(Shot).filter(Shot.scene_id == s.id).order_by(Shot.number).all()
        entry = {"scene_number": s.number, "shots": []}
        for sh in shots:
            shot_by_id[str(sh.id)] = sh
            entry["shots"].append({
                "id": str(sh.id),
                "duration": sh.estimated_duration_seconds or 5,
                "has_dialogue": bool((sh.dialogue or "").strip()),
            })
        scene_plan.append(entry)
    lines = [{"scene_number": r.scene_number, "line_index": r.line_index,
              "duration": r.duration_seconds or 0.0} for r in rows]
    changes = fit_shot_durations(scene_plan, lines)
    for shot_id, seconds in changes.items():
        shot_by_id[shot_id].estimated_duration_seconds = seconds
    if changes:
        db.commit()
    return len(changes)
