from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
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


@dataclass
class NarrativeMemoryGraph:
    project_id: str
    version: int = 0
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    characters: dict[str, CharacterState] = field(default_factory=dict)
    facts: list[NarrativeFact] = field(default_factory=list)
    motifs: list[VisualMotif] = field(default_factory=list)
    tension_curve: list[TensionPoint] = field(default_factory=list)
    prompt_history: list[PromptRecord] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)
    open_flags: list[dict] = field(default_factory=list)

    # ── Serialization ─────────────────────────────────────────

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "NarrativeMemoryGraph":
        nmg = cls(project_id=data["project_id"])
        nmg.version = data.get("version", 0)
        nmg.last_updated = data.get("last_updated", datetime.now(timezone.utc).isoformat())

        for name, char_data in data.get("characters", {}).items():
            scene_states = {}
            for sn, ss in char_data.get("scene_states", {}).items():
                scene_states[int(sn)] = SceneCharacterState(**ss)
            char_data_copy = {k: v for k, v in char_data.items() if k != "scene_states"}
            nmg.characters[name] = CharacterState(**char_data_copy, scene_states=scene_states)

        for f in data.get("facts", []):
            nmg.facts.append(NarrativeFact(**f))

        for m in data.get("motifs", []):
            nmg.motifs.append(VisualMotif(**m))

        for t in data.get("tension_curve", []):
            nmg.tension_curve.append(TensionPoint(**t))

        for p in data.get("prompt_history", []):
            nmg.prompt_history.append(PromptRecord(**p))

        nmg.relationships = data.get("relationships", [])
        nmg.open_flags = data.get("open_flags", [])
        return nmg

    # ── Read methods ──────────────────────────────────────────

    def get_character_context(self, character_name: str, scene_number: int) -> str:
        key = character_name.lower()
        char = self.characters.get(key)
        if not char:
            return ""
        parts = [char.visual_description]
        nearest_scene = None
        for sn in sorted(char.scene_states.keys()):
            if sn <= scene_number:
                nearest_scene = sn
        if nearest_scene is not None:
            state = char.scene_states[nearest_scene]
            parts.append(f"At this point: {state.emotional_state}.")
            if state.knows_about:
                parts.append(f"Knows about: {', '.join(state.knows_about)}.")
        return " ".join(parts)

    def get_established_facts(self, scene_number: int, categories: list[str] | None = None) -> list[str]:
        results = []
        for f in self.facts:
            if f.scene_number < scene_number and f.contradicted_by is None:
                if categories is None or f.category in categories:
                    results.append(f.fact)
        return results

    def get_visual_motifs_for_scene(self, scene_number: int) -> list[str]:
        return [m.prompt_fragment for m in self.motifs if scene_number in m.scenes_present or scene_number >= m.first_scene]

    def get_tension_at_scene(self, scene_number: int) -> TensionPoint | None:
        for tp in self.tension_curve:
            if tp.scene_number == scene_number:
                return tp
        return None

    def check_contradiction(self, proposed_fact: str, scene_number: int) -> bool:
        established = self.get_established_facts(scene_number)
        proposed_lower = proposed_fact.lower()
        for fact in established:
            if fact.lower() in proposed_lower or proposed_lower in fact.lower():
                return True
        return False

    def get_open_flags_for_scene(self, scene_number: int) -> list[dict]:
        return [f for f in self.open_flags if f.get("scene_number") == scene_number and f.get("status") == "OPEN"]

    def get_prompt_history_for_shot(self, shot_id: str) -> list[PromptRecord]:
        return [p for p in self.prompt_history if p.shot_id == shot_id]

    # ── Write methods ─────────────────────────────────────────

    def register_character(self, character: CharacterState) -> None:
        self.characters[character.name.lower()] = character
        self.version += 1
        self.last_updated = datetime.now(timezone.utc).isoformat()

    def update_character_state(self, character_name: str, scene_number: int, state: SceneCharacterState) -> None:
        key = character_name.lower()
        if key in self.characters:
            self.characters[key].scene_states[scene_number] = state
            self.version += 1
            self.last_updated = datetime.now(timezone.utc).isoformat()

    def record_fact(self, fact: NarrativeFact) -> None:
        self.facts.append(fact)
        self.version += 1
        self.last_updated = datetime.now(timezone.utc).isoformat()

    def register_motif(self, motif: VisualMotif) -> None:
        self.motifs.append(motif)
        self.version += 1

    def set_tension_curve(self, tension_points: list[TensionPoint]) -> None:
        self.tension_curve = tension_points
        self.version += 1
        self.last_updated = datetime.now(timezone.utc).isoformat()

    def record_prompt(self, record: PromptRecord) -> None:
        self.prompt_history.append(record)
        self.version += 1

    def resolve_flag(self, flag_id: str, resolution: str) -> None:
        for flag in self.open_flags:
            if flag.get("flag_id") == flag_id:
                flag["status"] = resolution
                self.version += 1
                break
