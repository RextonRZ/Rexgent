import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.final_export import FinalExport
from app.schemas.export import ExportRequest, ExportResult
from app.services.oss_manager import OSSManager
from app.config import get_settings
from app.workers.export_worker import run_export

from app.deps import get_current_user

router = APIRouter(prefix="/api/export", tags=["export"],
                   # every pipeline endpoint requires a signed-in user
                   dependencies=[Depends(get_current_user)])


@router.post("/{project_id}/audio")
async def upload_audio(project_id: str, file: UploadFile = File(...)):
    """Upload a music track for the export; returns its public URL."""
    content = await file.read()
    ext = (file.filename or "music.mp3").rsplit(".", 1)[-1].lower()
    if ext not in {"mp3", "wav", "m4a", "aac", "ogg"}:
        ext = "mp3"
    oss = OSSManager(get_settings())
    key = oss.get_project_path(project_id, "exports", f"music.{ext}")
    url = oss.upload_bytes(content, key, content_type=file.content_type or "audio/mpeg")
    return {"url": url}


@router.post("/{project_id}/media")
async def upload_media(project_id: str, file: UploadFile = File(...)):
    """Upload an external video clip to use in the cut; returns its public URL."""
    content = await file.read()
    ext = (file.filename or "clip.mp4").rsplit(".", 1)[-1].lower()
    if ext not in {"mp4", "mov", "webm", "m4v"}:
        ext = "mp4"
    oss = OSSManager(get_settings())
    key = oss.get_project_path(project_id, "media", f"{uuid.uuid4()}.{ext}")
    url = oss.upload_bytes(content, key, content_type=file.content_type or "video/mp4")
    return {"url": url}


@router.post("/render")
async def render_export(request: ExportRequest, db: Session = Depends(get_db)):
    # Unified ordered clip list: each entry is a generated clip (id) or an
    # imported media URL, with per-clip trim.
    if request.clips:
        clips = [
            {
                "id": str(c.clip_id) if c.clip_id else None,
                "url": c.url,
                "in": c.trim_start,
                "out": c.trim_end,
            }
            for c in request.clips
        ]
    elif request.clip_ids:
        clips = [
            {"id": str(cid), "url": None, "in": 0.0, "out": None}
            for cid in request.clip_ids
        ]
    else:
        clips = None

    audio = None
    if request.audio_url:
        audio = {
            "url": request.audio_url,
            "volume": request.audio_volume,
            "fade_in": request.audio_fade_in,
            "fade_out": request.audio_fade_out,
            "duck": request.audio_duck,
        }
    # light the pipeline the instant the user clicks — the worker's own
    # "started" event only fires once celery picks the job up
    from app.websocket.emitter import emit
    emit("stage:progress", {"stage": "export", "status": "started",
         "agent": "Editor", "label": "Queueing the final cut"},
         str(request.project_id))
    run_export.delay(str(request.project_id), str(request.job_id), clips, audio)
    return {"status": "rendering", "message": "Export job started"}


@router.post("/preview_plan")
async def preview_plan(request: dict, db: Session = Depends(get_db)):
    """Dialogue segments for the editor's LIVE preview — computed by the very
    same placement code the export uses (build_cut_plan + place_dialogue), so
    the preview's captions and voices land exactly where the render will put
    them. Pure math, no ffmpeg: milliseconds, not minutes.

    Body: {project_id, entries: [{scene_number, duration, has_dialogue,
    text?}] in timeline order}."""
    project_id = request.get("project_id")
    entries = request.get("entries") or []
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id required")
    from app.workers.export_worker import build_cut_plan
    from app.services.audio_timeline import place_dialogue
    from app.models.line_audio import LineAudio
    from app.models.generated_clip import GeneratedClip

    # inject each clip's stored speech onset (trim-adjusted) so the preview
    # places every line where the mouth starts moving — same as the export
    onset_ids = [uuid.UUID(str(e["clip_id"])) for e in entries if e.get("clip_id")]
    onset_clips = ({str(c.id): c for c in
                    db.query(GeneratedClip).filter(GeneratedClip.id.in_(onset_ids)).all()}
                   if onset_ids else {})
    for e in entries:
        c = onset_clips.get(str(e.get("clip_id") or ""))
        pol = getattr(c, "audio_json", None) if c is not None else None
        raw = pol.get("onset") if isinstance(pol, dict) else None
        if e.get("has_dialogue") and raw is not None:
            tin = float(e.get("trim_start") or 0.0)
            dur = float(e.get("duration") or 0.0)
            e["speech_onset"] = min(max(0.0, float(raw) - tin), max(0.0, dur - 1.0))
    scene_plan = build_cut_plan(entries)
    line_rows = [
        {"scene_number": r.scene_number, "line_index": r.line_index,
         "audio_path": r.audio_url, "duration": r.duration_seconds or 0.0,
         "text": r.text, "character": r.character_name}
        for r in db.query(LineAudio)
        .filter(LineAudio.project_id == uuid.UUID(project_id))
        .order_by(LineAudio.scene_number, LineAudio.line_index)
        .all()
        if r.audio_url
    ]
    segments = place_dialogue(line_rows, scene_plan)

    # per-chunk audio policy: the STORED verdict every export will also use
    chunks = []
    for e in entries:
        c = onset_clips.get(str(e.get("clip_id") or ""))
        pol = getattr(c, "audio_json", None) if c is not None else None
        if isinstance(pol, dict) and "mute" in pol:
            chunks.append({"mute": bool(pol.get("mute")), "volume": pol.get("volume")})
        elif c is not None:
            # no stored verdict yet — match the export's safe default so the
            # preview never plays fake speech the render would mute
            chunks.append({"mute": bool(e.get("has_dialogue")), "volume": None})
        else:
            chunks.append({"mute": False, "volume": None})  # imported media

    return {"segments": [
        {"start": s["start"], "duration": s.get("duration", 0.0),
         "text": s.get("text"), "character": s.get("character"),
         "audio_url": s.get("audio_path")}
        for s in segments
    ], "chunks": chunks}


@router.get("/{project_id}/download_all")
async def download_all(project_id: str, db: Session = Depends(get_db)):
    """One zip with every episode of the latest export (plus caption files)."""
    export = (
        db.query(FinalExport)
        .filter(FinalExport.project_id == uuid.UUID(project_id))
        .order_by(FinalExport.created_at.desc())
        .first()
    )
    if not export:
        raise HTTPException(status_code=404, detail="No export found")
    episodes = (export.report_json or {}).get("episodes") or []
    files = [{"name": f"episode_{d['episode']}.mp4", "url": d.get("url")}
             for d in episodes if d.get("url")]
    for d in episodes:
        if d.get("caption_url"):
            files.append({"name": f"episode_{d['episode']}.srt", "url": d["caption_url"]})
    if not files and export.url:
        files = [{"name": "final.mp4", "url": export.url}]
        if export.caption_url:
            files.append({"name": "captions.srt", "url": export.caption_url})
    if not files:
        raise HTTPException(status_code=404, detail="Nothing downloadable yet")

    import io as _io
    import zipfile
    import httpx as _httpx
    buf = _io.BytesIO()
    async with _httpx.AsyncClient() as http:
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
            for f in files:
                r = await http.get(f["url"], timeout=300.0)
                r.raise_for_status()
                z.writestr(f["name"], r.content)
    buf.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="episodes.zip"'})


@router.get("/{project_id}/download")
async def get_download(project_id: str, db: Session = Depends(get_db)):
    export = (
        db.query(FinalExport)
        .filter(FinalExport.project_id == uuid.UUID(project_id))
        .order_by(FinalExport.created_at.desc())
        .first()
    )
    if not export:
        raise HTTPException(status_code=404, detail="No export found")

    result = ExportResult.model_validate(export).model_dump()
    result["download_url"] = export.url
    return result
