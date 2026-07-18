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


def test_tight_two_shot_becomes_ots_when_speaker_known():
    # widening every tight two-shot to MS made a whole conversation render
    # as a wall of Medium Shots. When the speaker is known, the Director's
    # tight intent survives as an OTS: the speaker faces camera over the
    # listener's foreground shoulder — classic shot/reverse-shot.
    from app.services.storyboard_generator import widen_tight_two_shots
    shots = [
        {"shot_type": "MCU", "characters_in_frame": ["ANGELINE", "LUCAS"],
         "dialogue": "Why won't you help me?"},
        {"shot_type": "CU", "characters_in_frame": ["LUCAS", "ANGELINE"],
         "dialogue": "I told you, I don't know anything!"},
    ]
    lines = [{"character": "Angeline", "line": "Why won't you help me?"},
             {"character": "Lucas", "line": "I told you, I don't know anything!"}]
    widen_tight_two_shots(shots, dialogue_lines=lines)
    assert shots[0]["shot_type"] == "OTS"
    assert shots[0]["foreground_characters"] == ["LUCAS"]   # listener's shoulder
    assert shots[1]["shot_type"] == "OTS"
    assert shots[1]["foreground_characters"] == ["ANGELINE"]


def test_tight_two_shot_still_widens_without_a_speaker():
    # no dialogue lines (or a speaker not in frame): the safe MS widen stands
    from app.services.storyboard_generator import widen_tight_two_shots
    shots = [
        {"shot_type": "MCU", "characters_in_frame": ["A", "B"], "dialogue": None},
        {"shot_type": "MCU", "characters_in_frame": ["A", "B"],
         "dialogue": "Someone off-screen speaks."},
    ]
    lines = [{"character": "NARRATOR", "line": "Someone off-screen speaks."}]
    widen_tight_two_shots(shots, dialogue_lines=lines)
    assert shots[0]["shot_type"] == "MS"
    assert shots[1]["shot_type"] == "MS"


def test_tight_three_shot_widens_even_with_speaker():
    # OTS is a two-hander geometry: three or more in frame still widens
    from app.services.storyboard_generator import widen_tight_two_shots
    shots = [{"shot_type": "MCU", "characters_in_frame": ["A", "B", "C"],
              "dialogue": "Line."}]
    widen_tight_two_shots(shots, dialogue_lines=[{"character": "A", "line": "Line."}])
    assert shots[0]["shot_type"] == "MS"


def test_default_solo_subject_is_absorbed_not_presenting():
    # a solo default staged facing camera reads like a TV host; the subject
    # should be turned into their own action instead
    from app.services.storyboard_generator import _default_subjects
    solo = _default_subjects(["Angeline"])[0]
    assert solo["facing"] != "camera"
    assert "what they are doing" in solo["eyeline"]


def test_action_named_cast_joins_the_frame():
    # 'Angeline, holding Snowy, ...' with in_frame=[Angeline, John] rendered
    # a generic dog: Snowy's name was in the ACTION but not the cast, so his
    # plate and species fragment never rode and the sanitizer ate his name
    from app.services.storyboard_generator import _ensure_action_cast_in_frame
    out = _ensure_action_cast_in_frame(
        ["Angeline", "John"], "Angeline, holding Snowy, looks at John.",
        ["Angeline", "John", "Snowy"])
    assert out == ["Angeline", "John", "Snowy"]
    # dialogue-only mentions do NOT add anyone (handled elsewhere), and cast
    # already present is never duplicated
    out2 = _ensure_action_cast_in_frame(["Angeline"], "She kneels alone.",
                                        ["Angeline", "Snowy"])
    assert out2 == ["Angeline"]


# ── reorient wide: a tight hook opener gets a room-locking wide after it ────

def _tight_opener_scene():
    return [
        {"shot_number": 1, "shot_type": "MCU", "characters_in_frame": ["ANGELINE"],
         "dialogue": None, "action": "Angeline sobs under the bed, searching.",
         "emotional_beat": "Desperation", "lighting": "NATURAL", "colour_mood": "WARM",
         "subjects": [{"character": "ANGELINE", "posture": "kneeling",
                       "screen_side": "center"}]},
        {"shot_number": 2, "shot_type": "MS", "characters_in_frame": ["CLAIRE", "ANGELINE"],
         "dialogue": "Sweetheart, what's wrong?", "action": "Claire enters, concerned.",
         "subjects": [{"character": "CLAIRE"}, {"character": "ANGELINE"}]},
    ]


def test_tight_opener_gets_reorient_wide():
    # s1: the hook opens under the bed (MCU) and the next MS invented its own
    # room — with no wide established, fresh r2v shots drift the set. A brief
    # silent wide after the opener locks the room; later shots chain from it.
    from app.services.storyboard_generator import insert_reorient_wide
    shots = _tight_opener_scene()
    out = insert_reorient_wide(shots, "Angeline's room")
    assert len(out) == 3
    wide = out[1]
    assert wide["shot_type"] == "LS"
    assert not (wide.get("dialogue") or "")
    assert wide["characters_in_frame"] == ["ANGELINE"]   # the opener's cast
    assert "Angeline's room" in wide["action"]
    # blocking carried over so postures persist, but COPIED, never shared
    assert wide["subjects"][0]["posture"] == "kneeling"
    wide["subjects"][0]["posture"] = "standing"
    assert shots[0]["subjects"][0]["posture"] == "kneeling"


def test_wide_opener_is_left_alone():
    from app.services.storyboard_generator import insert_reorient_wide
    shots = _tight_opener_scene()
    shots[0]["shot_type"] = "LS"
    assert len(insert_reorient_wide(shots, "the room")) == 2


def test_no_reorient_when_second_shot_is_already_wide():
    from app.services.storyboard_generator import insert_reorient_wide
    shots = _tight_opener_scene()
    shots[1]["shot_type"] = "FS"
    assert len(insert_reorient_wide(shots, "the room")) == 2


def test_no_reorient_for_single_shot_scene():
    from app.services.storyboard_generator import insert_reorient_wide
    shots = [_tight_opener_scene()[0]]
    assert len(insert_reorient_wide(shots, "the room")) == 1


def _ots_shot(speaker_fg=True):
    subs = [
        {"character": "Claire", "frame_position": "foreground" if speaker_fg else "background",
         "screen_side": "left", "facing": "right"},
        {"character": "Angeline", "frame_position": "background" if speaker_fg else "foreground",
         "screen_side": "right", "facing": "left"},
    ]
    return {"shot_type": "OTS", "dialogue": "Angeline, wait!",
            "characters_in_frame": ["Claire", "Angeline"],
            "foreground_characters": ["Claire"] if speaker_fg else ["Angeline"],
            "blocking_json": {"subjects": subs}}


def test_face_the_speaker_moves_speaker_off_the_ots_shoulder():
    # LLM-boarded OTS put the SPEAKER in the foreground — the foreground of
    # an OTS is the back-of-head shoulder, so Claire pleaded her line as the
    # back of a head. The pass flips the geometry: listener is the shoulder,
    # the speaker faces camera.
    from app.services.storyboard_generator import face_the_speaker
    s = _ots_shot(speaker_fg=True)
    notes = face_the_speaker([s], dialogue_lines=[{"character": "Claire"}])
    assert s["foreground_characters"] == ["Angeline"]
    subs = {x["character"]: x for x in s["blocking_json"]["subjects"]}
    assert subs["Claire"]["frame_position"] != "foreground"
    assert subs["Angeline"]["frame_position"] == "foreground"
    assert notes


def test_face_the_speaker_leaves_correct_ots_alone():
    from app.services.storyboard_generator import face_the_speaker
    s = _ots_shot(speaker_fg=False)
    notes = face_the_speaker([s], dialogue_lines=[{"character": "Claire"}])
    assert s["foreground_characters"] == ["Angeline"]
    subs = {x["character"]: x for x in s["blocking_json"]["subjects"]}
    assert subs["Angeline"]["frame_position"] == "foreground"
    assert notes == []


def test_face_the_speaker_ignores_non_ots_and_silent_shots():
    from app.services.storyboard_generator import face_the_speaker
    ms = {"shot_type": "MS", "dialogue": "hello",
          "characters_in_frame": ["A", "B"],
          "blocking_json": {"subjects": [
              {"character": "A", "frame_position": "foreground"},
              {"character": "B", "frame_position": "background"}]}}
    silent = _ots_shot(speaker_fg=True)
    silent["dialogue"] = ""
    notes = face_the_speaker([ms, silent], dialogue_lines=[{"character": "A"}])
    assert ms["blocking_json"]["subjects"][0]["frame_position"] == "foreground"
    assert notes == []


def test_face_the_speaker_reads_board_level_subjects():
    # at the pipeline call point the board dicts carry top-level "subjects";
    # blocking_json is only assembled at row creation
    from app.services.storyboard_generator import face_the_speaker
    s = {"shot_type": "OTS", "dialogue": "Angeline, wait!",
         "characters_in_frame": ["Claire", "Angeline"],
         "foreground_characters": ["Claire"],
         "subjects": [
             {"character": "Claire", "frame_position": "foreground"},
             {"character": "Angeline", "frame_position": "background"}]}
    notes = face_the_speaker([s], dialogue_lines=[{"character": "Claire"}])
    subs = {x["character"]: x for x in s["subjects"]}
    assert subs["Claire"]["frame_position"] == "background"
    assert subs["Angeline"]["frame_position"] == "foreground"
    assert s["foreground_characters"] == ["Angeline"]
    assert notes
