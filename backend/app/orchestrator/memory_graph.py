"""Plain data-transfer objects for narrative entities.

The aggregate state + persistence that used to live here has moved to the
real graph layer in `app.graph.narrative_graph.NarrativeGraph` (Neo4j).
These dataclasses remain as lightweight DTOs passed between services.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SceneCharacterState:
    scene_number: int
    emotional_state: str
    physical_location: str
    knows_about: list[str] = field(default_factory=list)
    relationship_states: dict[str, str] = field(default_factory=dict)


@dataclass
class CharacterState:
    name: str
    role: str
    mbti: str
    face_embedding: list[float] = field(default_factory=list)
    visual_description: str = ""
    reference_image_url: Optional[str] = None
    scene_states: dict[int, SceneCharacterState] = field(default_factory=dict)
    established_appearance_notes: list[str] = field(default_factory=list)


@dataclass
class NarrativeFact:
    fact_id: str
    scene_number: int
    category: str
    fact: str
    established_by: str
    contradicted_by: Optional[str] = None


@dataclass
class VisualMotif:
    motif_id: str
    name: str
    description: str
    first_scene: int
    scenes_present: list[int] = field(default_factory=list)
    prompt_fragment: str = ""


@dataclass
class TensionPoint:
    scene_number: int
    tension_score: float
    beat_type: str
    reasoning: str = ""


@dataclass
class PromptRecord:
    shot_id: str
    scene_number: int
    prompt: str
    model_used: str
    output_url: Optional[str] = None
    consistency_score: Optional[float] = None
    retries: int = 0
    final_status: str = "PENDING"
