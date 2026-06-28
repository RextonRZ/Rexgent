import json
from dataclasses import asdict
from app.orchestrator.memory_graph import (
    NarrativeMemoryGraph,
    CharacterState,
    SceneCharacterState,
    NarrativeFact,
    VisualMotif,
    TensionPoint,
    PromptRecord,
)


# ── Serialization tests ──────────────────────────────────────

def test_nmg_creates_empty():
    nmg = NarrativeMemoryGraph(project_id="proj-123")
    assert nmg.project_id == "proj-123"
    assert nmg.version == 0
    assert nmg.characters == {}
    assert nmg.facts == []


def test_nmg_serializes_to_json():
    nmg = NarrativeMemoryGraph(project_id="proj-123")
    nmg.characters["yuki"] = CharacterState(
        name="Yuki", role="PROTAGONIST", mbti="INTJ",
        face_embedding=[0.1, 0.2, 0.3],
        visual_description="young detective with short black hair",
    )
    nmg.facts.append(NarrativeFact(
        fact_id="fact-001", scene_number=1, category="CHARACTER",
        fact="Yuki is a detective in Tokyo", established_by="dialogue",
    ))
    data = asdict(nmg)
    json_str = json.dumps(data, default=str)
    parsed = json.loads(json_str)
    assert parsed["characters"]["yuki"]["name"] == "Yuki"
    assert len(parsed["facts"]) == 1


def test_nmg_deserializes_from_json():
    nmg = NarrativeMemoryGraph(project_id="proj-123")
    nmg.facts.append(NarrativeFact(
        fact_id="f1", scene_number=1, category="LOCATION",
        fact="Story is set in Tokyo", established_by="stage_direction",
    ))
    data = asdict(nmg)
    json_str = json.dumps(data, default=str)
    restored = NarrativeMemoryGraph.from_dict(json.loads(json_str))
    assert restored.project_id == "proj-123"
    assert len(restored.facts) == 1
    assert restored.facts[0].fact == "Story is set in Tokyo"


# ── Helper to build a populated NMG ──────────────────────────

def make_populated_nmg():
    nmg = NarrativeMemoryGraph(project_id="proj-123")
    nmg.characters["yuki"] = CharacterState(
        name="Yuki", role="PROTAGONIST", mbti="INTJ",
        face_embedding=[0.1, 0.2],
        visual_description="young detective, short black hair, leather jacket",
        scene_states={
            1: SceneCharacterState(scene_number=1, emotional_state="guarded", physical_location="office", knows_about=["case file"], relationship_states={"aria": "colleague"}),
            3: SceneCharacterState(scene_number=3, emotional_state="suspicious", physical_location="rooftop", knows_about=["case file", "aria anomaly"], relationship_states={"aria": "distrustful"}),
        },
    )
    nmg.facts.append(NarrativeFact(fact_id="f1", scene_number=1, category="LOCATION", fact="Story is set in 2047 Tokyo", established_by="stage_direction"))
    nmg.facts.append(NarrativeFact(fact_id="f2", scene_number=2, category="CHARACTER", fact="ARIA is an AI", established_by="dialogue"))
    nmg.tension_curve.append(TensionPoint(scene_number=1, tension_score=3.0, beat_type="SETUP", reasoning="introduction"))
    nmg.tension_curve.append(TensionPoint(scene_number=3, tension_score=8.0, beat_type="CLIMAX", reasoning="confrontation"))
    nmg.prompt_history.append(PromptRecord(shot_id="shot-001", scene_number=1, prompt="test prompt", model_used="wan2.7"))
    return nmg


# ── Read method tests ─────────────────────────────────────────

def test_get_character_context():
    nmg = make_populated_nmg()
    ctx = nmg.get_character_context("yuki", 3)
    assert "young detective" in ctx
    assert "suspicious" in ctx


def test_get_character_context_before_first_scene():
    nmg = make_populated_nmg()
    ctx = nmg.get_character_context("yuki", 0)
    assert "young detective" in ctx


def test_get_character_context_unknown():
    nmg = make_populated_nmg()
    ctx = nmg.get_character_context("nobody", 1)
    assert ctx == ""


def test_get_established_facts():
    nmg = make_populated_nmg()
    facts = nmg.get_established_facts(2)
    assert len(facts) == 1
    assert "2047 Tokyo" in facts[0]


def test_get_established_facts_with_category():
    nmg = make_populated_nmg()
    facts = nmg.get_established_facts(3, categories=["CHARACTER"])
    assert len(facts) == 1
    assert "ARIA" in facts[0]


def test_get_tension_at_scene():
    nmg = make_populated_nmg()
    tp = nmg.get_tension_at_scene(3)
    assert tp.tension_score == 8.0
    assert tp.beat_type == "CLIMAX"


def test_get_tension_at_missing_scene():
    nmg = make_populated_nmg()
    tp = nmg.get_tension_at_scene(99)
    assert tp is None


def test_get_prompt_history_for_shot():
    nmg = make_populated_nmg()
    history = nmg.get_prompt_history_for_shot("shot-001")
    assert len(history) == 1
    assert history[0].model_used == "wan2.7"


def test_get_prompt_history_empty():
    nmg = make_populated_nmg()
    history = nmg.get_prompt_history_for_shot("nonexistent")
    assert history == []


# ── Write method tests ────────────────────────────────────────

def test_register_character():
    nmg = NarrativeMemoryGraph(project_id="proj-123")
    nmg.register_character(CharacterState(
        name="Yuki", role="PROTAGONIST", mbti="INTJ",
        visual_description="detective",
    ))
    assert "yuki" in nmg.characters
    assert nmg.characters["yuki"].name == "Yuki"
    assert nmg.version == 1


def test_update_character_state():
    nmg = NarrativeMemoryGraph(project_id="proj-123")
    nmg.register_character(CharacterState(
        name="Yuki", role="PROTAGONIST", mbti="INTJ",
        visual_description="detective",
    ))
    nmg.update_character_state("yuki", 2, SceneCharacterState(
        scene_number=2, emotional_state="angry",
        physical_location="rooftop", knows_about=["truth"],
        relationship_states={},
    ))
    assert 2 in nmg.characters["yuki"].scene_states
    assert nmg.characters["yuki"].scene_states[2].emotional_state == "angry"


def test_record_fact():
    nmg = NarrativeMemoryGraph(project_id="proj-123")
    nmg.record_fact(NarrativeFact(
        fact_id="f1", scene_number=1, category="LOCATION",
        fact="Set in Tokyo", established_by="dialogue",
    ))
    assert len(nmg.facts) == 1
    assert nmg.version == 1


def test_set_tension_curve():
    nmg = NarrativeMemoryGraph(project_id="proj-123")
    nmg.set_tension_curve([
        TensionPoint(scene_number=1, tension_score=3.0, beat_type="SETUP"),
        TensionPoint(scene_number=2, tension_score=7.0, beat_type="RISING"),
    ])
    assert len(nmg.tension_curve) == 2


def test_record_prompt():
    nmg = NarrativeMemoryGraph(project_id="proj-123")
    nmg.record_prompt(PromptRecord(
        shot_id="s1", scene_number=1, prompt="test", model_used="wan2.7",
    ))
    assert len(nmg.prompt_history) == 1


def test_resolve_flag():
    nmg = NarrativeMemoryGraph(project_id="proj-123")
    nmg.open_flags.append({"flag_id": "f1", "scene_number": 1, "status": "OPEN"})
    nmg.resolve_flag("f1", "FIXED")
    assert nmg.open_flags[0]["status"] == "FIXED"


def test_resolve_flag_nonexistent():
    nmg = NarrativeMemoryGraph(project_id="proj-123")
    nmg.open_flags.append({"flag_id": "f1", "scene_number": 1, "status": "OPEN"})
    nmg.resolve_flag("nonexistent", "FIXED")
    assert nmg.open_flags[0]["status"] == "OPEN"  # unchanged
