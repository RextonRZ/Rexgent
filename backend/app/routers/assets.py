"""Read-only Asset Library API: search assets and suggest music by drama mood.
The AssetManager is the reusable core; a future Music/Editing Agent calls the
same manager methods directly."""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user
from app.database import get_db
from app.services.asset_manager import AssetManager
from app.services.music_suggest import derive_mood

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assets", tags=["assets"],
                   dependencies=[Depends(get_current_user)])

_manager = AssetManager()
_manager.scan()

# Resolved library URLs are cached by asset id: resolve_url uploads to a
# deterministic shared key, so the first search pays the upload and later ones
# reuse the URL instead of re-uploading on a read-only GET.
_url_cache: dict[str, str] = {}


def _serialize(asset, resolve=True):
    out = asset.model_dump()
    if resolve:
        url = _url_cache.get(asset.id)
        if url is None:
            try:
                url = _manager.resolve_url(asset)
                _url_cache[asset.id] = url
            except Exception:  # noqa: BLE001 - a serving hiccup shouldn't fail the search
                logger.warning("asset: resolve_url failed for %s", asset.id, exc_info=True)
                url = None
        out["url"] = url
    return out


@router.get("/music/suggest")
def suggest_music(project_id: str, db: Session = Depends(get_db)):
    from app.models.project import Project
    from app.models.script import Script, Scene
    import uuid
    project = db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
    genre = getattr(project, "genre", None) if project else None
    beats = []
    if project:
        script = (db.query(Script).filter(Script.project_id == project.id)
                  .order_by(Script.created_at.desc()).first())
        if script:
            beats = [s.emotional_beat for s in db.query(Scene)
                     .filter(Scene.script_id == script.id).all() if s.emotional_beat]
    mood = derive_mood(genre=genre, beats=beats)
    return {"mood": mood,
            "results": [_serialize(a) for a in _manager.find_music(mood=mood)]}


@router.get("/{asset_type}")
def search_assets(asset_type: str, mood: str | None = None, scene: str | None = None,
                  max_duration: float | None = None, intensity: int | None = None):
    results = _manager.find(asset_type, mood=mood, scene=scene,
                            max_duration=max_duration, intensity=intensity)
    return {"results": [_serialize(a) for a in results]}
