from pydantic import BaseModel
from uuid import UUID
from typing import Optional


class GenerationStartRequest(BaseModel):
    project_id: UUID


class GenerationJobStatus(BaseModel):
    id: UUID
    status: str
    total_shots: Optional[int] = None
    completed_shots: int = 0
    estimated_cost: Optional[float] = None
    actual_cost: float = 0.0

    model_config = {"from_attributes": True}


class ClipResult(BaseModel):
    id: UUID
    shot_id: UUID
    model_used: Optional[str] = None
    url: Optional[str] = None
    consistency_score: Optional[float] = None
    # bible references that conditioned this clip ([{url, role, character?}])
    references_json: Optional[list] = None
    seed: Optional[int] = None
    status: str
    retries: int = 0
    cost_usd: Optional[float] = None
    # the clip's REAL probed duration (models render short of the request)
    duration_seconds: Optional[float] = None

    model_config = {"from_attributes": True}
