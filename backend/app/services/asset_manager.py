"""File-based Asset Library index. Scans <root>/<type>/<category>/*.json sidecars,
validates each against its schema, and answers search/random queries. No DB, no OSS
— the OSS bridge (resolve_url) lives on top and is only used when an asset ships."""
import json
import logging
import random
from pathlib import Path

from app.assets.registry import ASSET_TYPES
from app.assets.schema import AssetMeta, schema_for

logger = logging.getLogger(__name__)


class AssetManager:
    def __init__(self, root: str | Path | None = None):
        from app.config import get_settings
        default = Path(__file__).resolve().parents[2] / "assets"  # backend/assets
        self.root = Path(root) if root else Path(getattr(get_settings(), "asset_root", "") or default)
        self._index: dict[str, list[AssetMeta]] = {}

    def scan(self) -> None:
        """Build the in-memory index from sidecar JSONs. Called once (or refresh)."""
        index: dict[str, list[AssetMeta]] = {t: [] for t in ASSET_TYPES}
        for t in ASSET_TYPES:
            type_dir = self.root / t
            if not type_dir.exists():
                continue
            for jf in type_dir.rglob("*.json"):
                try:
                    data = json.loads(jf.read_text(encoding="utf-8"))
                    data.setdefault("type", t)
                    meta = schema_for(t)(**data)
                    meta.__dict__["_dir"] = str(jf.parent)
                    index[t].append(meta)
                except Exception as e:  # noqa: BLE001 — a bad sidecar is skipped, never fatal
                    logger.warning("asset: skipped invalid metadata %s: %s", jf, e)
        self._index = index

    def refresh(self) -> None:
        self.scan()

    def all(self, asset_type: str) -> list[AssetMeta]:
        if not self._index:
            self.scan()
        return list(self._index.get(asset_type, []))

    def find(self, asset_type: str, **criteria) -> list[AssetMeta]:
        """Filter by equality, plus max_duration and list-membership for scene/tags."""
        return [a for a in self.all(asset_type) if self._matches(a, criteria)]

    @staticmethod
    def _matches(a: AssetMeta, criteria: dict) -> bool:
        for k, v in criteria.items():
            if v is None:
                continue
            if k == "max_duration":
                if a.duration is not None and a.duration > v:
                    return False
            elif k == "scene":
                if v not in (getattr(a, "scene_tags", None) or []):
                    return False
            elif k == "tag":
                if v not in (a.tags or []):
                    return False
            else:
                if getattr(a, k, None) != v:
                    return False
        return True

    def find_music(self, mood=None, scene=None, max_duration=None, intensity=None):
        return self.find("music", mood=mood, scene=scene, max_duration=max_duration,
                         intensity=intensity)

    def find_ambience(self, environment=None):
        return self.find("ambience", tag=environment) if environment else self.all("ambience")

    def find_transition(self, style=None):
        return self.find("transitions", tag=style) if style else self.all("transitions")

    def random_match(self, asset_type: str, **criteria) -> AssetMeta | None:
        hits = self.find(asset_type, **criteria)
        return random.choice(hits) if hits else None  # noqa: S311 — non-crypto pick

    def local_path(self, asset: AssetMeta) -> Path:
        """The on-disk file for an asset (its sidecar dir + filename)."""
        return Path(asset.__dict__.get("_dir", str(self.root))) / asset.filename

    def resolve_url(self, asset, oss=None) -> str:
        """Upload the library file to a SHARED (non-per-project) OSS key and return
        the public URL, so the export/frontend can consume it. Idempotent enough:
        the same asset always maps to the same key, so re-uploads just overwrite."""
        from app.services.oss_manager import OSSManager
        from app.config import get_settings
        oss = oss or OSSManager(get_settings())
        key = f"library/{asset.type}/{asset.filename}"
        return oss.upload_file(str(self.local_path(asset)), key)
