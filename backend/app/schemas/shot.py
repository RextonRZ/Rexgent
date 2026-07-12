from pydantic import BaseModel
from uuid import UUID
from typing import Optional


class ShotCreate(BaseModel):
    scene_id: UUID
    number: int
    shot_type: Optional[str] = None
    camera_movement: Optional[str] = None
    lighting: Optional[str] = None
    colour_mood: Optional[str] = None
    action: Optional[str] = None
    dialogue: Optional[str] = None
    emotional_beat: Optional[str] = None
    estimated_duration_seconds: int = 5
    quality_tier: Optional[str] = None
    characters_in_frame: Optional[list[str]] = None
    notes: Optional[str] = None
    director_note: Optional[str] = None


class ShotResponse(BaseModel):
    id: UUID
    scene_id: UUID
    number: int
    shot_type: Optional[str] = None
    camera_movement: Optional[str] = None
    lighting: Optional[str] = None
    colour_mood: Optional[str] = None
    action: Optional[str] = None
    dialogue: Optional[str] = None
    emotional_beat: Optional[str] = None
    estimated_duration_seconds: int
    quality_tier: Optional[str] = None
    characters_in_frame: Optional[list[str]] = None
    notes: Optional[str] = None
    director_note: Optional[str] = None
    # absolute per-shot geometry: {"subjects": [{character, frame_position,
    # screen_side, facing, eyeline, action}], "reverse_angle": bool}
    blocking_json: Optional[dict] = None
    prompt_json: Optional[dict] = None

    model_config = {"from_attributes": True}
