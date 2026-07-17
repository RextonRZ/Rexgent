import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.storyboard_generator import (
    StoryboardGenerator,
    fit_duration_to_dialogue,
)


def test_short_line_gets_base_clip_length():
    assert fit_duration_to_dialogue("Riku! What did you do?") == 5


def test_no_dialogue_action_beat_is_base_length():
    assert fit_duration_to_dialogue(None) == 5
    assert fit_duration_to_dialogue("") == 5


def test_long_line_gets_a_longer_clip():
    long_line = (
        "And so, the great Riku Sato, master of mischief, faced his greatest "
        "challenge yet, standing tall against the towering fury of his mother "
        "and the shattered remains of the family vase."
    )
    assert fit_duration_to_dialogue(long_line) == 10


@pytest.mark.asyncio
async def test_generate_sizes_clips_to_their_dialogue():
    gen = StoryboardGenerator.__new__(StoryboardGenerator)
    long_line = " ".join(["word"] * 40)  # ~15s of speech -> capped tier
    gen.qwen = MagicMock()
    gen.qwen.chat_json = AsyncMock(return_value=[
        {"shot_number": 1, "shot_type": "MS", "camera_movement": "STATIC",
         "characters_in_frame": [], "action": "x", "dialogue": "Short line.",
         "lighting": "NATURAL", "colour_mood": "WARM", "emotional_beat": "x",
         "estimated_duration_seconds": 99, "notes": ""},
        {"shot_number": 2, "shot_type": "MS", "camera_movement": "STATIC",
         "characters_in_frame": [], "action": "x", "dialogue": long_line,
         "lighting": "NATURAL", "colour_mood": "WARM", "emotional_beat": "x",
         "estimated_duration_seconds": 1, "notes": ""},
    ])
    gen.prompt_template = "placeholder"
    shots = await gen.generate_for_scene(
        scene_json={"dialogue": [{"line": "Short line."}, {"line": long_line}]},
        characters_in_scene=[])
    # LLM's own number is ignored; length is derived from the line
    assert shots[0]["estimated_duration_seconds"] == 5
    assert shots[1]["estimated_duration_seconds"] == 10


@pytest.mark.asyncio
async def test_generate_returns_shots():
    gen = StoryboardGenerator.__new__(StoryboardGenerator)
    gen.qwen = MagicMock()
    gen.qwen.chat_json = AsyncMock(return_value=[
        {"shot_number": 1, "shot_type": "EWS", "camera_movement": "DRONE", "characters_in_frame": [], "action": "Rain-soaked street", "dialogue": None, "lighting": "NEON", "colour_mood": "DESATURATED", "emotional_beat": "dread", "estimated_duration_seconds": 4, "notes": ""},
        {"shot_number": 2, "shot_type": "CU", "camera_movement": "STATIC", "characters_in_frame": ["YUKI"], "action": "Yuki stares", "dialogue": "Something's wrong.", "lighting": "DRAMATIC_SIDE", "colour_mood": "COOL", "emotional_beat": "tension", "estimated_duration_seconds": 5, "notes": ""},
    ])
    gen.prompt_template = "placeholder"

    result = await gen.generate_for_scene(scene_json={"scene_number": 1}, characters_in_scene=[])
    assert len(result) == 2
    assert result[0]["shot_type"] == "EWS"
    assert result[1]["characters_in_frame"] == ["YUKI"]


@pytest.mark.asyncio
async def test_generate_handles_non_list():
    gen = StoryboardGenerator.__new__(StoryboardGenerator)
    gen.qwen = MagicMock()
    gen.qwen.chat_json = AsyncMock(return_value={"bad": "shape"})
    gen.prompt_template = "placeholder"

    result = await gen.generate_for_scene(scene_json={}, characters_in_scene=[])
    assert result == []


@pytest.mark.asyncio
async def test_scene_dialogue_reaches_the_prompt_verbatim():
    gen = StoryboardGenerator.__new__(StoryboardGenerator)
    captured = {}

    async def fake_chat_json(messages, **kw):
        captured["user"] = messages[-1]["content"]
        return [{
            "shot_number": 1, "shot_type": "MS", "camera_movement": "STATIC",
            "characters_in_frame": ["EMI"], "action": "Emi on the phone",
            "dialogue": "Yes, I understand, Mrs. Tanaka.",
            "lighting": "NATURAL", "colour_mood": "WARM",
            "emotional_beat": "calm", "estimated_duration_seconds": 5, "notes": "",
        }]

    gen.qwen = MagicMock()
    gen.qwen.chat_json = fake_chat_json
    gen.prompt_template = "placeholder"

    scene = {
        "scene_number": 1,
        "heading": "INT. SATO LIVING ROOM - DAY",
        "dialogue": [{"character": "EMI", "line": "Yes, I understand, Mrs. Tanaka."}],
        "stage_directions": ["Emi is on the phone, keeping her voice calm."],
    }
    result = await gen.generate_for_scene(scene_json=scene, characters_in_scene=[])

    # the real line must be visible to the model, and preserved on the shot
    assert "Yes, I understand, Mrs. Tanaka." in captured["user"]
    assert result[0]["dialogue"] == "Yes, I understand, Mrs. Tanaka."


@pytest.mark.asyncio
async def test_shot_budget_grows_to_cover_every_line():
    gen = StoryboardGenerator.__new__(StoryboardGenerator)
    returned = [
        {"shot_number": i, "shot_type": "MS", "camera_movement": "STATIC",
         "characters_in_frame": [], "action": "x", "dialogue": f"line {i}",
         "lighting": "NATURAL", "colour_mood": "WARM", "emotional_beat": "x",
         "estimated_duration_seconds": 5, "notes": ""}
        for i in range(8)
    ]
    gen.qwen = MagicMock()
    gen.qwen.chat_json = AsyncMock(return_value=returned)
    gen.prompt_template = "placeholder"

    scene = {"scene_number": 1,
             "dialogue": [{"character": "X", "line": f"line {i}"} for i in range(8)]}
    # base budget of 3 must not truncate an 8-line scene
    result = await gen.generate_for_scene(
        scene_json=scene, characters_in_scene=[], max_shots=3)
    assert len(result) == 8


@pytest.mark.asyncio
async def test_shot_budget_capped_for_runaway_scene():
    gen = StoryboardGenerator.__new__(StoryboardGenerator)
    returned = [
        {"shot_number": i, "shot_type": "MS", "camera_movement": "STATIC",
         "characters_in_frame": [], "action": "x", "dialogue": f"line {i}",
         "lighting": "NATURAL", "colour_mood": "WARM", "emotional_beat": "x",
         "estimated_duration_seconds": 5, "notes": ""}
        for i in range(30)
    ]
    gen.qwen = MagicMock()
    gen.qwen.chat_json = AsyncMock(return_value=returned)
    gen.prompt_template = "placeholder"

    scene = {"scene_number": 1,
             "dialogue": [{"character": "X", "line": f"l{i}"} for i in range(30)]}
    result = await gen.generate_for_scene(scene_json=scene, characters_in_scene=[])
    assert len(result) == StoryboardGenerator._HARD_CAP


@pytest.mark.asyncio
async def test_reveal_pairs_get_budget_headroom():
    # react-then-reveal beats are TWO shots; the budget line must say so or
    # the cap squeezes the pair back into one crammed frame
    gen = StoryboardGenerator.__new__(StoryboardGenerator)
    gen.qwen = MagicMock()
    gen.qwen.chat_json = AsyncMock(return_value=[])
    gen.prompt_template = "placeholder"

    await gen.generate_for_scene(
        {"scene_number": 1, "dialogue": ["a", "b"]}, [], max_shots=2)
    user_msg = gen.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "react-then-reveal pair" in user_msg


def test_template_stages_reveals_as_two_shots():
    from app.services.prompt_loader import load_prompt
    t = load_prompt("storyboard_generate.txt")
    assert "REACT-THEN-REVEAL" in t
    assert "TWO consecutive shots" in t
    assert "eyeline OFF-camera toward" in t
    # the old single-shot reveal instruction must be gone
    assert "never make the reveal a two-shot that splits attention" not in t


def test_strip_noncast_action_drops_the_offscreen_sentence():
    # scene 1 shot 3 cast only ANGELINE, but the action kept "Theo quickly
    # stands up too" — the model rendered a second person from that sentence
    from app.services.storyboard_generator import strip_noncast_action
    action = ("Angeline, determined, wipes her tears and stands up, holding "
              "the hutch. Theo quickly stands up too, nodding in agreement.")
    out = strip_noncast_action(action, ["ANGELINE"], ["ANGELINE", "THEO"])
    assert "Theo" not in out
    assert "wipes her tears" in out


def test_strip_noncast_action_keeps_offscreen_addressees():
    # a cast member ADDRESSING an off-screen character is fine — only
    # sentences that stage the non-cast person themselves are dropped
    from app.services.storyboard_generator import strip_noncast_action
    action = "Mrs. Jones smiles and confirms she saw Theo earlier, looking at both Angeline and Theo."
    out = strip_noncast_action(action, ["MRS. JONES"], ["MRS. JONES", "ANGELINE", "THEO"])
    assert out == action


def test_strip_noncast_action_never_returns_empty():
    from app.services.storyboard_generator import strip_noncast_action
    action = "Theo stands in the doorway."
    out = strip_noncast_action(action, ["ANGELINE"], ["ANGELINE", "THEO"])
    assert out  # a fully-dropped action falls back to the original


def test_tight_two_shot_widens_to_ms():
    # an MCU cannot hold two people: the render showed one while the stage
    # diagram promised both — tight framings with 2+ cast widen to MS
    from app.services.storyboard_generator import widen_tight_two_shots
    shots = [
        {"shot_type": "MCU", "characters_in_frame": ["ANGELINE", "THEO"]},
        {"shot_type": "MCU", "characters_in_frame": ["ANGELINE"]},
        {"shot_type": "CU", "characters_in_frame": ["A", "B"]},
        {"shot_type": "OTS", "characters_in_frame": ["A", "B"]},
    ]
    notes = widen_tight_two_shots(shots)
    assert shots[0]["shot_type"] == "MS"
    assert shots[1]["shot_type"] == "MCU"   # a single stays tight
    assert shots[2]["shot_type"] == "MS"
    assert shots[3]["shot_type"] == "OTS"   # OTS is BUILT for two people
    assert len(notes) == 2


def test_default_solo_subject_is_absorbed_not_presenting():
    # a solo default staged facing camera reads like a TV host; the subject
    # should be turned into their own action instead
    from app.services.storyboard_generator import _default_subjects
    solo = _default_subjects(["Angeline"])[0]
    assert solo["facing"] != "camera"
    assert "what they are doing" in solo["eyeline"]
