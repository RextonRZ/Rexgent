from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, Any


class ScriptResponse(BaseModel):
    id: UUID
    project_id: UUID
    raw_text: Optional[str] = None
    structured_json: Optional[dict[str, Any]] = None
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SceneResponse(BaseModel):
    id: UUID
    script_id: UUID
    number: int
    title: Optional[str] = None
    heading: Optional[str] = None
    location: Optional[str] = None
    time_of_day: Optional[str] = None
    description: Optional[str] = None
    emotional_beat: Optional[str] = None

    model_config = {"from_attributes": True}


class ScriptParseResponse(BaseModel):
    script_id: UUID
    raw_text: str
    structured_json: dict[str, Any]
    characters_mentioned: list[str]


class ScriptGenerateRequest(BaseModel):
    project_id: UUID
    genre: str
    premise: str
    tone: str = "dramatic"
    episode_count: int = 1
    target_length: int = 5
    notes: Optional[str] = None


class ScriptGenerateResponse(BaseModel):
    script_id: UUID
    raw_text: str
    structured_json: dict[str, Any]
    characters_mentioned: list[str]


class ScriptUpdateRequest(BaseModel):
    raw_text: Optional[str] = None
