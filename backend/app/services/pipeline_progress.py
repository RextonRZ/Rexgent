"""Which pipeline stages have REAL artifacts — one source of truth.

Drives the step nav (GET /progress) AND grounds the Showrunner chat, so
"what's my next step" is answered from the same facts the UI shows. Done
means data exists, not merely visited.
"""
STAGE_ORDER = ["script", "characters", "storyboard", "generate", "export"]

STAGE_PAGES = {
    "script": "the Script page",
    "characters": "the Characters page",
    "storyboard": "the Storyboard page",
    "generate": "the Generate page",
    "export": "the Edit & Export page",
}

STAGE_LABELS = {
    "script": "Script",
    "characters": "Characters",
    "storyboard": "Storyboard",
    "generate": "Generate",
    "export": "Edit & Export",
}

# what to actually DO there — shown on the chat's go-to-page card
STAGE_HINTS = {
    "script": "Write or import your script, or flip Full Auto and let the agent write, judge and revise it for you.",
    "characters": "Extract the cast from the script, then generate plates to lock each face, costume and location.",
    "storyboard": "Generate the storyboard to break every scene into shots with set dressing.",
    "generate": "Start generation. The plan is fitted to your spend cap, hook shots protected on the premium tier.",
    "export": "Arrange the cut, pick music, then render the final vertical episode with voices and captions.",
}


def next_step_card(progress: dict) -> dict:
    """Structured guidance for the chat UI: where to go and what to do there.
    Deterministic — computed from artifacts, never from the LLM."""
    stage = next_stage(progress)
    if stage is None:
        return {"stage": "done", "path": "export", "label": "Edit & Export",
                "hint": "All stages are complete. Rewatch the episode or re-render a new cut."}
    return {"stage": stage, "path": stage, "label": STAGE_LABELS[stage],
            "hint": STAGE_HINTS[stage]}


def stage_progress(db, project_id) -> dict:
    from app.models.script import Script, Scene
    from app.models.shot import Shot
    from app.models.character import Character
    from app.models.generation_job import GenerationJob
    from app.models.generated_clip import GeneratedClip
    from app.models.final_export import FinalExport

    script = (db.query(Script).filter(Script.project_id == project_id)
              .order_by(Script.created_at.desc()).first())
    has_script = bool(script and (script.raw_text or "").strip())
    has_characters = db.query(Character).filter(
        Character.project_id == project_id).count() > 0
    has_shots = False
    if script:
        scene_ids = [s.id for s in
                     db.query(Scene.id).filter(Scene.script_id == script.id).all()]
        if scene_ids:
            has_shots = db.query(Shot).filter(Shot.scene_id.in_(scene_ids)).count() > 0
    job_ids = [j.id for j in db.query(GenerationJob.id)
               .filter(GenerationJob.project_id == project_id).all()]
    has_clips = bool(job_ids) and db.query(GeneratedClip).filter(
        GeneratedClip.job_id.in_(job_ids), GeneratedClip.url.isnot(None)).count() > 0
    has_export = db.query(FinalExport).filter(
        FinalExport.project_id == project_id).count() > 0
    return {"script": has_script, "characters": has_characters,
            "storyboard": has_shots, "generate": has_clips, "export": has_export}


def next_stage(progress: dict) -> str | None:
    """First incomplete stage in pipeline order, or None when all done."""
    for stage in STAGE_ORDER:
        if not progress.get(stage):
            return stage
    return None
