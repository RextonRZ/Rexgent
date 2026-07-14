"""Asset metadata schemas. Sidecar JSON beside each asset is validated against
these. `extra="allow"` keeps future keys, so older assets never break when the
format grows."""
from pydantic import BaseModel, ConfigDict


class AssetMeta(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    title: str
    filename: str
    type: str
    tags: list[str] = []
    duration: float | None = None
    license: str | None = None
    attribution: str | None = None
    source: str | None = None


class MusicMeta(AssetMeta):
    mood: str
    scene_tags: list[str] = []
    tempo: str | None = None
    intensity: int = 1
    instruments: list[str] = []
    loopable: bool = False


SCHEMA_BY_TYPE: dict[str, type[AssetMeta]] = {"music": MusicMeta}


def schema_for(asset_type: str) -> type[AssetMeta]:
    return SCHEMA_BY_TYPE.get(asset_type, AssetMeta)
