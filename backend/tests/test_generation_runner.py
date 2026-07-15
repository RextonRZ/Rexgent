import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import app.services.generation_runner as gr
from app.services.generation_runner import GenerationRunner


def _make_dispatch_runner():
    runner = GenerationRunner.__new__(GenerationRunner)
    runner.qwen = MagicMock()
    return runner


def test_is_catastrophic_flags_black_and_faceless_renders():
    from app.services.generation_runner import _is_catastrophic
    # the Shot-3 case: face-locked character in frame, no face found, black bg
    assert _is_catastrophic({"continuity_score": 50, "face_score": None, "background_score": 0.1}, ["MIAO JING"]) is True
    # near-zero continuity is garbage
    assert _is_catastrophic({"continuity_score": 10, "face_score": 0.8, "background_score": 0.9}, ["A"]) is True
    # a face was expected but none rendered
    assert _is_catastrophic({"continuity_score": 55, "face_score": None, "background_score": 0.9}, ["A"]) is True


def test_is_catastrophic_ignores_good_and_soft_misses():
    from app.services.generation_runner import _is_catastrophic
    # a good render
    assert _is_catastrophic({"continuity_score": 90, "face_score": 0.88, "background_score": 0.95}, ["A"]) is False
    # a SOFT miss (mediocre face/bg) is not catastrophic — it ships flagged, no re-roll
    assert _is_catastrophic({"continuity_score": 55, "face_score": 0.42, "background_score": 0.6}, ["A"]) is False
    # an insert/establishing with no characters + no face is fine
    assert _is_catastrophic({"continuity_score": 80, "face_score": None, "background_score": 0.9}, []) is False


@pytest.fixture(autouse=True)
def _no_ws(monkeypatch):
    """Keep tests isolated from Redis/WebSocket, OSS re-hosting, and the cost ledger."""
    monkeypatch.setattr(gr, "emit", lambda *a, **k: None)
    monkeypatch.setattr(gr, "record_video", lambda *a, **k: 0.54)
    monkeypatch.setattr(gr, "report_agent", lambda *a, **k: None)
    monkeypatch.setattr(gr, "persist_clip_url", lambda pid, hint, url: url)
    # Isolate every test from the local .env: baseline the routing/feature flags
    # to their code defaults so a developer's .env (e.g. IDENTITY_ROUTING_V2=true)
    # can't flip a legacy-path test. Tests that need a flag on monkeypatch it True.
    for _flag in ("identity_routing_v2", "repair_enabled", "multishot_enabled",
                  "happyhorse_native_talk",
                  "wan_on_same_cast", "image_ref_labels", "wan_primary",
                  "route_continuation_to_happyhorse", "cinematic_prompt"):
        monkeypatch.setattr(gr.get_settings(), _flag, False, raising=False)


def make_runner():
    runner = GenerationRunner.__new__(GenerationRunner)
    runner.db = MagicMock()
    runner.oss = MagicMock()
    runner.oss.get_project_path = MagicMock(return_value="k")
    runner.oss.upload_bytes = MagicMock(return_value="frameurl")
    runner.qwen = MagicMock()
    runner.qwen.generate_video_happyhorse = AsyncMock(return_value="task1")
    runner.qwen.generate_video_wan = AsyncMock(return_value="task1")
    runner.qwen.generate_video_wan_r2v = AsyncMock(return_value="task1")
    runner.qwen.poll_video_task = AsyncMock(return_value="http://x/clip.mp4")
    runner.prompt_crafter = MagicMock()
    runner.prompt_crafter.craft = AsyncMock(return_value={"prompt": "base prompt"})
    runner.continuity = MagicMock()
    runner.budget_ceiling = 34.0
    return runner


def make_shot():
    return SimpleNamespace(
        id="shot1", number=1, shot_type="CU", camera_movement="STATIC", action="x",
        lighting="NATURAL", colour_mood="COOL", emotional_beat="tension",
        dialogue="YUKI: We need to move.", estimated_duration_seconds=5,
        quality_tier="happyhorse", characters_in_frame=["Yuki"])


def make_char():
    return SimpleNamespace(
        name="Yuki", face_vector=[0.1] * 512, video_prompt_fragment="young detective",
        visual_description="young detective", face_embedding={}, reference_image_url=None)


BIBLE = {"characters": {"Yuki": {"variants": [
    {"plate_image_url": "y", "scene_numbers": [1], "is_default": True}]}},
    "location_by_scene": {1: "loc"}, "style_plate": "style"}


@pytest.mark.asyncio
async def test_passing_clip_is_approved(monkeypatch):
    runner = make_runner()
    runner.continuity.validate = AsyncMock(return_value={
        "continuity_score": 82, "overall_pass": True,
        "face_score": 0.8, "outfit_score": 0.7, "background_score": 0.6})
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    await runner._process_shot(job, make_shot(), {"Yuki": make_char()}, BIBLE, 1, None)
    added = runner.db.add.call_args[0][0]
    assert added.status == "APPROVED"
    assert added.consistency_score == 82
    assert job.completed_shots == 1


@pytest.mark.asyncio
async def test_process_shot_records_video_cost(monkeypatch):
    runner = make_runner()
    runner.continuity.validate = AsyncMock(return_value={
        "continuity_score": 80, "overall_pass": True,
        "face_score": 0.8, "outfit_score": 0.7, "background_score": 0.6})
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    calls = {}
    monkeypatch.setattr(gr, "record_video", lambda *a, **k: calls.setdefault("n", 0) or calls.update(n=calls.get("n", 0) + 1) or 0.54)
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    await runner._process_shot(job, make_shot(), {"Yuki": make_char()}, BIBLE, 1, None)
    assert calls.get("n") == 1


@pytest.mark.asyncio
async def test_clip_records_reference_provenance_and_seed(monkeypatch):
    runner = make_runner()
    runner.continuity.validate = AsyncMock(return_value={
        "continuity_score": 82, "overall_pass": True,
        "face_score": 0.8, "outfit_score": 0.7, "background_score": 0.6})
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    await runner._process_shot(job, make_shot(), {"Yuki": make_char()}, BIBLE, 1, "prevframe")
    added = runner.db.add.call_args[0][0]
    roles = {p["role"] for p in added.references_json}
    # CU shot: ONE character plate (face + outfit) + last-frame chain + style; NO location
    assert roles == {"character", "prev_frame", "style"}
    ident = next(p for p in added.references_json if p["role"] == "character")
    assert ident["character"] == "Yuki"
    # deterministic seed, stored AND sent to the video model
    assert added.seed == gr.stable_seed("p1", "shot1")
    kwargs = runner.qwen.generate_video_happyhorse.await_args.kwargs
    assert kwargs["seed"] == added.seed
    # vertical by default — the short-drama delivery format
    assert kwargs["ratio"] == "9:16"


@pytest.mark.asyncio
async def test_landscape_drama_renders_16_9(monkeypatch):
    runner = make_runner()
    runner._video_ratio = "16:9"  # the user picked landscape at creation
    runner.continuity.validate = AsyncMock(return_value={
        "continuity_score": 82, "overall_pass": True,
        "face_score": 0.8, "outfit_score": 0.7, "background_score": 0.6})
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    await runner._process_shot(job, make_shot(), {"Yuki": make_char()}, BIBLE, 1, None)
    kwargs = runner.qwen.generate_video_happyhorse.await_args.kwargs
    assert kwargs["ratio"] == "16:9"


@pytest.mark.asyncio
async def test_scene_anchor_and_setting_flow_into_shot(monkeypatch):
    runner = make_runner()
    runner.continuity.validate = AsyncMock(return_value={
        "continuity_score": 82, "overall_pass": True,
        "face_score": 0.8, "outfit_score": 0.7, "background_score": 0.6})
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    setting = {"location": "living room",
               "set_items": ["blue vase on the oak table"]}
    await runner._process_shot(job, make_shot(), {"Yuki": make_char()}, BIBLE, 1,
                               "prevframe", scene_anchor_url="anchorframe",
                               scene_setting=setting)
    added = runner.db.add.call_args[0][0]
    roles = {p["role"] for p in added.references_json}
    assert "scene_anchor" in roles
    # the crafted prompt received the scene setting (rule 13 injection)
    craft_kwargs = runner.prompt_crafter.craft.await_args.kwargs
    assert craft_kwargs["scene_setting"] == setting


@pytest.mark.asyncio
async def test_low_continuity_flags_not_retries(monkeypatch):
    runner = make_runner()
    runner.continuity.validate = AsyncMock(return_value={
        "continuity_score": 30, "overall_pass": False,
        "face_score": 0.3, "outfit_score": 0.4, "background_score": 0.5})
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    await runner._process_shot(job, make_shot(), {"Yuki": make_char()}, BIBLE, 1, None)
    # generated exactly once — NO soft retry on a low continuity score
    assert runner.qwen.generate_video_happyhorse.await_count == 1
    added = runner.db.add.call_args[0][0]
    assert added.status == "NEEDS_REVIEW"


@pytest.mark.asyncio
async def test_hard_failure_retries_then_needs_review(monkeypatch):
    runner = make_runner()
    runner.qwen.poll_video_task = AsyncMock(side_effect=RuntimeError("api down"))
    runner.continuity.validate = AsyncMock()
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    await runner._process_shot(job, make_shot(), {"Yuki": make_char()}, BIBLE, 1, None)
    added = runner.db.add.call_args[0][0]
    assert added.status == "NEEDS_REVIEW"
    # hard failure retries up to MAX_RETRIES(=1) -> 2 total attempts
    assert runner.qwen.generate_video_happyhorse.await_count == 2


# --- wan continuation routing: plain first-frame -> happyhorse fallback ---

def _continuity_pass():
    return AsyncMock(return_value={
        "continuity_score": 82, "overall_pass": True,
        "face_score": 0.8, "outfit_score": 0.7, "background_score": 0.6})


def _wan_shot():
    shot = make_shot()
    shot.quality_tier = "wan"
    return shot


LINE = {"audio_url": "http://a/line.mp3", "character_name": "Yuki",
        "duration": 4.0}  # fits the 5s shot


@pytest.mark.asyncio
async def test_wan_shot_without_frame_anchor_renders_on_happyhorse(monkeypatch):
    """No frame to continue from: wan cannot carry a face, and wan2.7-r2v holds
    identity worse than happyhorse r2v (measured ~46 vs ~67 continuity), so the
    shot renders on happyhorse r2v with the bible plates."""
    runner = make_runner()
    runner.continuity.validate = _continuity_pass()
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    monkeypatch.setattr(gr, "get_settings",
                        lambda: SimpleNamespace(lipsync_enabled=True))
    seen = {}

    def fake_record(db, pid, duration, tier, ref_id=None):
        seen["tier"] = tier
        return 0.54
    monkeypatch.setattr(gr, "record_video", fake_record)
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    await runner._process_shot(job, _wan_shot(), {"Yuki": make_char()}, BIBLE, 1,
                               None, lipsync_line=LINE)
    assert runner.qwen.generate_video_wan.await_count == 0
    assert runner.qwen.generate_video_wan_r2v.await_count == 0
    assert runner.qwen.generate_video_happyhorse.await_count == 1
    assert runner.qwen.generate_video_happyhorse.await_args.kwargs["mode"] == "r2v"
    # the tier that ACTUALLY rendered — clip row and cost ledger agree
    added = runner.db.add.call_args[0][0]
    assert added.model_used == "happyhorse"
    assert seen["tier"] == "happyhorse"


@pytest.mark.asyncio
async def test_scenes_run_concurrently_under_semaphore():
    import asyncio
    from app.services.generation_runner import GenerationRunner
    runner = GenerationRunner.__new__(GenerationRunner)
    runner._max_concurrency = 5
    order = []

    async def fake_scene(scene, bible):
        order.append(("start", scene))
        await asyncio.sleep(0.01)
        order.append(("end", scene))

    runner._run_scene = fake_scene
    await runner._run_scenes_concurrently(scenes=[1, 2, 3], bible={})
    # scenes run in parallel: all three start before any ends
    assert order[:3] == [("start", 1), ("start", 2), ("start", 3)]
    assert len(order) == 6


def test_load_bible_shapes_characters_and_locations():
    from app.services.generation_runner import GenerationRunner
    runner = GenerationRunner.__new__(GenerationRunner)

    class V: pass
    v = V(); v.plate_image_url = "u"; v.scene_numbers = [1]; v.is_default = True
    import numpy as np
    v.face_vector = np.array([0.1, 0.2])  # pgvector returns numpy arrays

    class C: pass
    c = C(); c.name = "Mia"; c.costume_variants = [v]

    class L: pass
    l = L(); l.location_key = "cafe"; l.plate_image_url = "loc"; l.scene_numbers = [1]

    bible = runner._shape_bible(characters=[c], locations=[l], style_url="style")
    assert bible["characters"]["Mia"]["variants"][0]["plate_image_url"] == "u"
    # the continuity face-lock reads this — it must ride along as a PLAIN LIST
    # (a numpy array would crash the agent's `if not ref` truthiness check)
    assert bible["characters"]["Mia"]["variants"][0]["face_vector"] == [0.1, 0.2]
    assert bible["location_by_scene"][1] == "loc"
    assert bible["style_plate"] == "style"


@pytest.mark.asyncio
async def test_craft_prompt_resolves_bare_first_names_to_cast():
    """Shots boarded before name normalization store 'EIRIK' for 'Eirik
    Halden' — the crafted prompt must still carry his visual fragment, not
    silently drop him from character_visuals."""
    runner = make_runner()
    shot = SimpleNamespace(
        shot_type="MS", camera_movement="static", action="walks to the spot",
        lighting=None, colour_mood=None, emotional_beat=None, dialogue=None,
        estimated_duration_seconds=5, characters_in_frame=["EIRIK"],
        quality_tier="happyhorse",
    )
    char = SimpleNamespace(name="Eirik Halden",
                           video_prompt_fragment="tall athlete, long blonde hair",
                           visual_description="tall athlete")
    await runner._craft_prompt(shot, {"Eirik Halden": char})
    visuals = runner.prompt_crafter.craft.await_args.kwargs["character_visuals"]
    assert "Eirik Halden" in visuals
    assert visuals["Eirik Halden"]["video_prompt_fragment"] == "tall athlete, long blonde hair"


@pytest.mark.asyncio
async def test_wan_newcomer_routes_to_happyhorse_r2v_with_plates(monkeypatch):
    """A shot that INTRODUCES a face-locked character can't get identity from
    wan (it only continues the previous frame), and wan2.7-r2v holds a face
    worse than happyhorse r2v (measured ~46 vs ~67 continuity). So such shots
    render on happyhorse r2v, which carries the bible plates."""
    runner = make_runner()
    runner.continuity.validate = AsyncMock(return_value={
        "continuity_score": 80, "overall_pass": True,
        "face_score": 0.8, "outfit_score": 0.7, "background_score": 0.6})
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0,
                          completed_shots=0, total_shots=1)
    shot = make_shot()
    shot.quality_tier = "wan"
    shot.characters_in_frame = ["Jonas", "Yuki"]  # Jonas is NEW this shot
    bible = {"characters": {
        "Yuki": {"variants": [{"plate_image_url": "y", "scene_numbers": [1], "is_default": True}]},
        "Jonas": {"variants": [{"plate_image_url": "j", "scene_numbers": [1], "is_default": True}]},
    }, "location_by_scene": {1: "loc"}, "style_plate": "style"}

    await runner._process_shot(
        job, shot, {"Yuki": make_char()}, bible, 1,
        prev_last_frame_url="http://prev/frame.png",   # wan WOULD have continued
        prev_in_frame=["Yuki"])                         # ...but Jonas is new
    runner.qwen.generate_video_wan.assert_not_called()
    runner.qwen.generate_video_wan_r2v.assert_not_called()
    runner.qwen.generate_video_happyhorse.assert_awaited_once()
    kwargs = runner.qwen.generate_video_happyhorse.await_args.kwargs
    assert kwargs["mode"] == "r2v"
    assert any("j" == m.get("url") for m in kwargs["reference_media"])


@pytest.mark.asyncio
async def test_wan_keeps_the_shot_when_cast_continues(monkeypatch):
    """No newcomers: wan continues the scene from the previous frame as designed."""
    runner = make_runner()
    runner.continuity.validate = AsyncMock(return_value={
        "continuity_score": 80, "overall_pass": True,
        "face_score": 0.8, "outfit_score": 0.7, "background_score": 0.6})
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0,
                          completed_shots=0, total_shots=1)
    shot = make_shot()
    shot.quality_tier = "wan"

    await runner._process_shot(
        job, shot, {"Yuki": make_char()}, BIBLE, 1,
        prev_last_frame_url="http://prev/frame.png",
        prev_in_frame=["Yuki"])
    runner.qwen.generate_video_wan.assert_awaited_once()


@pytest.mark.asyncio
async def test_v2_anchor_shot_dispatches_r2v_with_ref_stack(monkeypatch):
    # anchor_ref_model="wan" -> ANCHOR role -> wan2.7-r2v with the reference stack.
    runner = _make_dispatch_runner()
    monkeypatch.setattr(gr.get_settings(), "anchor_ref_model", "wan", raising=False)
    runner.qwen.generate_video_wan_r2v = AsyncMock(return_value="task-r2v")
    runner.qwen.generate_video_wan = AsyncMock(return_value="task-wan")
    tier, task = await runner._dispatch_by_role(
        role="anchor", prompt="p", duration=5, seed=1, ratio="9:16", negative=None,
        ref_stack=[{"type": "reference_image", "url": "face.png"}],
        frame_anchor="prev.png", prev_clip_url=None)
    assert tier == "wan_r2v"
    runner.qwen.generate_video_wan_r2v.assert_awaited_once()
    # anchor gets NO first_frame (establishing), just the plates
    media = runner.qwen.generate_video_wan_r2v.await_args.kwargs["reference_media"]
    assert media == [{"type": "reference_image", "url": "face.png"}]


@pytest.mark.asyncio
async def test_v2_entrance_shot_adds_first_frame_to_r2v(monkeypatch):
    runner = _make_dispatch_runner()
    monkeypatch.setattr(gr.get_settings(), "anchor_ref_model", "wan", raising=False)
    runner.qwen.generate_video_wan_r2v = AsyncMock(return_value="task-r2v")
    tier, task = await runner._dispatch_by_role(
        role="entrance", prompt="p", duration=5, seed=1, ratio="9:16", negative=None,
        ref_stack=[{"type": "reference_image", "url": "newface.png"}],
        frame_anchor="prev.png", prev_clip_url=None)
    assert tier == "wan_r2v"
    media = runner.qwen.generate_video_wan_r2v.await_args.kwargs["reference_media"]
    assert media[0] == {"type": "first_frame", "url": "prev.png"}
    assert {"type": "reference_image", "url": "newface.png"} in media


@pytest.mark.asyncio
async def test_v2_continue_hold_silent_uses_first_clip(monkeypatch):
    runner = _make_dispatch_runner()
    runner.qwen.generate_video_wan = AsyncMock(return_value="task-wan")
    tier, task = await runner._dispatch_by_role(
        role="continue_hold", prompt="p", duration=5, seed=1, ratio="9:16", negative=None,
        ref_stack=None, frame_anchor="prev.png", prev_clip_url="clip.mp4")
    media = runner.qwen.generate_video_wan.await_args.kwargs["reference_media"]
    assert media == [{"type": "first_clip", "url": "clip.mp4"}]


@pytest.mark.asyncio
async def test_v2_r2v_failure_falls_back_to_happyhorse(monkeypatch):
    runner = _make_dispatch_runner()
    monkeypatch.setattr(gr.get_settings(), "anchor_ref_model", "wan", raising=False)
    runner.qwen.generate_video_wan_r2v = AsyncMock(side_effect=RuntimeError("boom"))
    runner.qwen.generate_video_happyhorse = AsyncMock(return_value="task-hh")
    tier, task = await runner._dispatch_by_role(
        role="anchor", prompt="p", duration=5, seed=1, ratio="9:16", negative=None,
        ref_stack=[{"type": "reference_image", "url": "f.png"}],
        frame_anchor=None, prev_clip_url=None)
    assert tier == "happyhorse"
    runner.qwen.generate_video_happyhorse.assert_awaited_once()


@pytest.mark.asyncio
async def test_v2_anchor_with_no_refs_falls_back_to_happyhorse():
    runner = _make_dispatch_runner()
    runner.qwen.generate_video_wan_r2v = AsyncMock(return_value="task-r2v")
    runner.qwen.generate_video_happyhorse = AsyncMock(return_value="task-hh")
    tier, task = await runner._dispatch_by_role(
        role="anchor", prompt="p", duration=5, seed=1, ratio="9:16", negative=None,
        ref_stack=None, frame_anchor=None, prev_clip_url=None)
    assert tier == "happyhorse"
    runner.qwen.generate_video_wan_r2v.assert_not_awaited()
    # no refs -> happyhorse runs in t2v mode
    assert runner.qwen.generate_video_happyhorse.await_args.kwargs["mode"] == "t2v"


@pytest.mark.asyncio
async def test_v2_continue_hold_with_no_media_falls_back_to_happyhorse():
    runner = _make_dispatch_runner()
    runner.qwen.generate_video_wan = AsyncMock(return_value="task-wan")
    runner.qwen.generate_video_happyhorse = AsyncMock(return_value="task-hh")
    tier, task = await runner._dispatch_by_role(
        role="continue_hold", prompt="p", duration=5, seed=1, ratio="9:16", negative=None,
        ref_stack=None, frame_anchor=None, prev_clip_url=None)
    assert tier == "happyhorse"
    runner.qwen.generate_video_wan.assert_not_awaited()


@pytest.mark.asyncio
async def test_v2_continue_hold_wan_failure_falls_back_to_happyhorse():
    runner = _make_dispatch_runner()
    runner.qwen.generate_video_wan = AsyncMock(side_effect=RuntimeError("boom"))
    runner.qwen.generate_video_happyhorse = AsyncMock(return_value="task-hh")
    tier, task = await runner._dispatch_by_role(
        role="continue_hold", prompt="p", duration=5, seed=1, ratio="9:16", negative=None,
        ref_stack=None, frame_anchor="prev.png", prev_clip_url="clip.mp4")
    assert tier == "happyhorse"
    runner.qwen.generate_video_happyhorse.assert_awaited_once()


@pytest.mark.asyncio
async def test_v2_reangle_adds_first_frame_to_r2v(monkeypatch):
    runner = _make_dispatch_runner()
    monkeypatch.setattr(gr.get_settings(), "anchor_ref_model", "wan", raising=False)
    runner.qwen.generate_video_wan_r2v = AsyncMock(return_value="task-r2v")
    tier, task = await runner._dispatch_by_role(
        role="continue_reangle", prompt="p", duration=5, seed=1, ratio="9:16", negative=None,
        ref_stack=[{"type": "reference_image", "url": "face.png"}],
        frame_anchor="prev.png", prev_clip_url=None)
    assert tier == "wan_r2v"
    media = runner.qwen.generate_video_wan_r2v.await_args.kwargs["reference_media"]
    assert media[0] == {"type": "first_frame", "url": "prev.png"}


@pytest.mark.asyncio
async def test_v2_anchor_defaults_to_happyhorse_r2v():
    # Default anchor_ref_model="happyhorse": identity shots render on happyhorse
    # r2v (measured to hold faces better than wan r2v), never wan r2v.
    runner = _make_dispatch_runner()
    runner.qwen.generate_video_wan_r2v = AsyncMock(return_value="task-r2v")
    runner.qwen.generate_video_happyhorse = AsyncMock(return_value="task-hh")
    tier, task = await runner._dispatch_by_role(
        role="anchor", prompt="p", duration=5, seed=1, ratio="9:16", negative=None,
        ref_stack=[{"type": "reference_image", "url": "face.png"}],
        frame_anchor=None, prev_clip_url=None)
    assert tier == "happyhorse"
    runner.qwen.generate_video_wan_r2v.assert_not_awaited()
    # happyhorse renders in r2v mode with the plate stack
    assert runner.qwen.generate_video_happyhorse.await_args.kwargs["mode"] == "r2v"
    media = runner.qwen.generate_video_happyhorse.await_args.kwargs["reference_media"]
    assert media == [{"type": "reference_image", "url": "face.png"}]


# --- identity_routing_v2 wired into _process_shot ---

@pytest.mark.asyncio
async def test_v2_process_shot_routes_continue_hold_when_flag_on(monkeypatch):
    """Flag ON: a same-cast, same-framing shot that HAS a frame anchor to
    continue from classifies as continue_hold and dispatches through
    _dispatch_by_role onto wan i2v continuation — never wan r2v."""
    runner = make_runner()
    runner.continuity.validate = AsyncMock(return_value={
        "continuity_score": 82, "overall_pass": True,
        "face_score": 0.8, "outfit_score": 0.7, "background_score": 0.6})
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    monkeypatch.setattr(gr.get_settings(), "identity_routing_v2", True, raising=False)
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    shot = make_shot()  # CU, characters_in_frame=["Yuki"]

    await runner._process_shot(
        job, shot, {"Yuki": make_char()}, BIBLE, 1,
        prev_last_frame_url="prevframe", prev_in_frame=["Yuki"],
        prev_shot_type="CU")

    runner.qwen.generate_video_wan.assert_awaited_once()
    runner.qwen.generate_video_wan_r2v.assert_not_awaited()
    added = runner.db.add.call_args[0][0]
    assert added.model_used == "wan"


@pytest.mark.asyncio
async def test_wan_primary_silent_continuation_threads_to_wan_into_craft(monkeypatch):
    """wan_primary + v2 ON: a silent same-cast continuation is a Wan visual shot,
    so the runner computes to_wan=True and threads it into the crafter (which
    appends the Wan SFX/no-dialogue/no-BGM tail). A speaking shot -> to_wan=False."""
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    monkeypatch.setattr(gr.get_settings(), "identity_routing_v2", True, raising=False)
    monkeypatch.setattr(gr.get_settings(), "wan_primary", True, raising=False)
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)

    # silent continuation -> to_wan True
    runner = make_runner()
    runner.continuity.validate = AsyncMock(return_value={
        "continuity_score": 82, "overall_pass": True,
        "face_score": 0.8, "outfit_score": 0.7, "background_score": 0.6})
    shot = make_shot(); shot.dialogue = None
    await runner._process_shot(job, shot, {"Yuki": make_char()}, BIBLE, 1,
                               prev_last_frame_url="prevframe", prev_in_frame=["Yuki"],
                               prev_shot_type="CU")
    assert runner.prompt_crafter.craft.await_args.kwargs["to_wan"] is True

    # a speaking shot is never a Wan visual shot -> to_wan False
    runner2 = make_runner()
    runner2.continuity.validate = AsyncMock(return_value={
        "continuity_score": 82, "overall_pass": True,
        "face_score": 0.8, "outfit_score": 0.7, "background_score": 0.6})
    shot2 = make_shot()  # carries dialogue
    await runner2._process_shot(job, shot2, {"Yuki": make_char()}, BIBLE, 1,
                                prev_last_frame_url="prevframe", prev_in_frame=["Yuki"],
                                prev_shot_type="CU")
    assert runner2.prompt_crafter.craft.await_args.kwargs["to_wan"] is False


@pytest.mark.asyncio
async def test_v2_entrance_on_nonwan_tier_routes_to_r2v(monkeypatch):
    """Flag ON: a face-locked NEWCOMER entering on a NON-wan (happyhorse) shot
    classifies as entrance and must render on wan r2v with a face reference —
    NOT wan i2v continuation, which carries no reference for the new face.
    Regression: newcomers must be computed for every tier, not just wan."""
    runner = make_runner()
    runner.continuity.validate = AsyncMock(return_value={
        "continuity_score": 82, "overall_pass": True,
        "face_score": 0.8, "outfit_score": 0.7, "background_score": 0.6})
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    monkeypatch.setattr(gr.get_settings(), "identity_routing_v2", True, raising=False)
    monkeypatch.setattr(gr.get_settings(), "anchor_ref_model", "wan", raising=False)
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    shot = make_shot()
    shot.quality_tier = "happyhorse"           # NON-wan planned tier
    shot.characters_in_frame = ["Jonas", "Yuki"]  # Jonas is NEW this shot
    bible = {"characters": {
        "Yuki": {"variants": [{"plate_image_url": "y", "scene_numbers": [1], "is_default": True}]},
        "Jonas": {"variants": [{"plate_image_url": "j", "scene_numbers": [1], "is_default": True}]},
    }, "location_by_scene": {1: "loc"}, "style_plate": "style"}

    await runner._process_shot(
        job, shot, {"Yuki": make_char()}, bible, 1,
        prev_last_frame_url="prevframe",   # frame anchor present
        prev_in_frame=["Yuki"],             # only Yuki was here before
        prev_shot_type="CU")                # same framing -> no angle change

    # entrance -> wan r2v with the newcomer's plate; NOT wan i2v continuation
    runner.qwen.generate_video_wan_r2v.assert_awaited_once()
    runner.qwen.generate_video_wan.assert_not_awaited()


@pytest.mark.asyncio
async def test_v2_process_shot_anchor_routes_to_r2v(monkeypatch):
    """Flag ON: NO frame anchor to continue from -> role anchor -> establishing
    render on wan r2v with the plate stack, never wan i2v continuation."""
    runner = make_runner()
    runner.continuity.validate = AsyncMock(return_value={
        "continuity_score": 82, "overall_pass": True,
        "face_score": 0.8, "outfit_score": 0.7, "background_score": 0.6})
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    monkeypatch.setattr(gr.get_settings(), "identity_routing_v2", True, raising=False)
    monkeypatch.setattr(gr.get_settings(), "anchor_ref_model", "wan", raising=False)
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    shot = make_shot()  # CU, characters_in_frame=["Yuki"] (Yuki has a plate)

    await runner._process_shot(
        job, shot, {"Yuki": make_char()}, BIBLE, 1,
        prev_last_frame_url=None, scene_anchor_url=None,  # NO frame anchor
        prev_in_frame=None, prev_shot_type=None)

    runner.qwen.generate_video_wan_r2v.assert_awaited_once()
    runner.qwen.generate_video_wan.assert_not_awaited()


@pytest.mark.asyncio
async def test_v2_process_shot_reangle_routes_to_r2v(monkeypatch):
    """Flag ON: same cast (no newcomer) with a frame anchor, but a DIFFERENT
    framing from the previous shot -> role continue_reangle -> wan r2v with
    first_frame + plates, never wan i2v continuation (which copies the frame)."""
    runner = make_runner()
    runner.continuity.validate = AsyncMock(return_value={
        "continuity_score": 82, "overall_pass": True,
        "face_score": 0.8, "outfit_score": 0.7, "background_score": 0.6})
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    monkeypatch.setattr(gr.get_settings(), "identity_routing_v2", True, raising=False)
    monkeypatch.setattr(gr.get_settings(), "anchor_ref_model", "wan", raising=False)
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    shot = make_shot()  # shot_type == "CU"

    await runner._process_shot(
        job, shot, {"Yuki": make_char()}, BIBLE, 1,
        prev_last_frame_url="prevframe",   # frame anchor present
        prev_in_frame=["Yuki"],             # same cast, no newcomer
        prev_shot_type="MS")                # MS -> CU: an angle change

    runner.qwen.generate_video_wan_r2v.assert_awaited_once()
    runner.qwen.generate_video_wan.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_shot_returns_actual_spend(monkeypatch):
    # _process_shot returns (frame_url, clip_url, spent); spent is the real
    # billed cost from record_video, so the caller can count it accurately.
    runner = make_runner()
    runner.continuity.validate = AsyncMock(return_value={
        "continuity_score": 82, "overall_pass": True,
        "face_score": 0.8, "outfit_score": 0.7, "background_score": 0.6})
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    monkeypatch.setattr(gr, "record_video", lambda *a, **k: 0.54)
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    result = await runner._process_shot(
        job, make_shot(), {"Yuki": make_char()}, BIBLE, 1,
        prev_last_frame_url="prevframe", prev_in_frame=["Yuki"], prev_shot_type="CU")
    assert result[2] == 0.54


@pytest.mark.asyncio
async def test_repair_reseeds_a_soft_fail_and_keeps_better(monkeypatch):
    # repair_enabled: a first render that fails continuity triggers a reseed;
    # the better-scoring re-render is kept (APPROVED), and BOTH renders are billed.
    runner = make_runner()
    scores = iter([
        {"continuity_score": 40, "overall_pass": False, "face_score": 0.3,
         "outfit_score": 0.8, "background_score": 0.8},   # first render fails
        {"continuity_score": 78, "overall_pass": True, "face_score": 0.8,
         "outfit_score": 0.8, "background_score": 0.8},    # reseed passes
    ])
    runner.continuity.validate = AsyncMock(side_effect=lambda **k: next(scores))
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    monkeypatch.setattr(gr, "record_video", lambda *a, **k: 0.5)
    monkeypatch.setattr(gr.get_settings(), "repair_enabled", True, raising=False)
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    result = await runner._process_shot(
        job, make_shot(), {"Yuki": make_char()}, BIBLE, 1,
        prev_last_frame_url="prevframe", prev_in_frame=["Yuki"], prev_shot_type="CU")
    added = runner.db.add.call_args[0][0]
    assert added.status == "APPROVED"            # kept the better re-render
    assert added.consistency_score == 78
    assert result[2] == 1.0                      # first render + reseed both billed (0.5 x 2)


@pytest.mark.asyncio
async def test_repair_disabled_ships_first_clip(monkeypatch):
    # repair OFF (default): a soft fail ships flagged, no re-render, one bill.
    runner = make_runner()
    runner.continuity.validate = AsyncMock(return_value={
        "continuity_score": 40, "overall_pass": False, "face_score": 0.3,
        "outfit_score": 0.8, "background_score": 0.8})
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    monkeypatch.setattr(gr, "record_video", lambda *a, **k: 0.5)
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    result = await runner._process_shot(
        job, make_shot(), {"Yuki": make_char()}, BIBLE, 1,
        prev_last_frame_url="prevframe", prev_in_frame=["Yuki"], prev_shot_type="CU")
    added = runner.db.add.call_args[0][0]
    assert added.status == "NEEDS_REVIEW"
    assert result[2] == 0.5                       # one render only


@pytest.mark.asyncio
async def test_repair_primary_bill_uses_first_render_tier(monkeypatch):
    # The primary booking must bill the FIRST render's tier even when a repair
    # of a DIFFERENT tier wins. Assert the model/tier arg to record_video.
    runner = make_runner()
    monkeypatch.setattr(gr.get_settings(), "identity_routing_v2", True, raising=False)
    monkeypatch.setattr(gr.get_settings(), "repair_enabled", True, raising=False)
    scores = iter([
        {"continuity_score": 40, "overall_pass": False, "face_score": 0.3,
         "outfit_score": 0.8, "background_score": 0.8},   # first render (wan) fails
        {"continuity_score": 80, "overall_pass": True, "face_score": 0.8,
         "outfit_score": 0.8, "background_score": 0.8},    # repair passes
    ])
    runner.continuity.validate = AsyncMock(side_effect=lambda **k: next(scores))

    async def fake_repair(step, **k):
        return ("http://x/repair.mp4", "happyhorse")      # a DIFFERENT tier than the first render
    monkeypatch.setattr(runner, "_run_repair_step", fake_repair)
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    billed = []
    monkeypatch.setattr(gr, "record_video",
                        lambda db, pid, secs, tier, **k: (billed.append(tier), 0.5)[1])
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    # same-cast, same-framing, frame anchor present -> continue_hold -> first render on wan
    await runner._process_shot(
        job, make_shot(), {"Yuki": make_char()}, BIBLE, 1,
        prev_last_frame_url="prevframe", prev_in_frame=["Yuki"], prev_shot_type="CU")
    assert "wan" in billed          # primary booking used first_tier (wan), NOT the winning repair tier
    assert "happyhorse" in billed   # the repair render was billed too


@pytest.mark.asyncio
async def test_repair_all_steps_fail_ships_first_and_bills_once(monkeypatch):
    # repair_enabled on, but every repair strategy yields nothing: the shot ships
    # the best (== first) clip flagged, and ONLY the primary booking bills.
    runner = make_runner()
    monkeypatch.setattr(gr.get_settings(), "repair_enabled", True, raising=False)
    runner.continuity.validate = AsyncMock(return_value={
        "continuity_score": 40, "overall_pass": False, "face_score": 0.3,
        "outfit_score": 0.8, "background_score": 0.8})

    async def fake_repair(step, **k):
        return (None, None)                                # every repair yields nothing
    monkeypatch.setattr(runner, "_run_repair_step", fake_repair)
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    calls = {"n": 0}
    monkeypatch.setattr(gr, "record_video",
                        lambda *a, **k: (calls.update(n=calls["n"] + 1), 0.5)[1])
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    result = await runner._process_shot(
        job, make_shot(), {"Yuki": make_char()}, BIBLE, 1,
        prev_last_frame_url="prevframe", prev_in_frame=["Yuki"], prev_shot_type="CU")
    added = runner.db.add.call_args[0][0]
    assert added.status == "NEEDS_REVIEW"    # ships the best/first clip, flagged
    assert calls["n"] == 1                    # only the primary booking billed
    assert result[2] == 0.5


@pytest.mark.asyncio
async def test_multishot_beat_renders_once_and_writes_a_clip_per_shot(monkeypatch):
    # flag ON: a 2-shot dialogue beat renders ONE wan clip and writes TWO clip
    # rows sharing that url with contiguous trims; cost booked once.
    runner = make_runner()
    runner.continuity.validate = AsyncMock(return_value={
        "continuity_score": 80, "overall_pass": True,
        "face_score": 0.8, "outfit_score": 0.7, "background_score": 0.6})
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    monkeypatch.setattr("app.services.video_stitcher.VideoStitcher._duration",
                        staticmethod(lambda p: 10.0))
    billed = []
    monkeypatch.setattr(gr, "record_video", lambda db, pid, secs, tier, **k: (billed.append(tier), 0.5)[1])
    monkeypatch.setattr(gr.get_settings(), "multishot_enabled", True, raising=False)
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=2)
    s1 = make_shot(); s1.number = 1; s1.characters_in_frame = ["Yuki"]; s1.dialogue = "YUKI: hi"
    s2 = make_shot(); s2.id = "shot2"; s2.number = 2; s2.characters_in_frame = ["Yuki"]; s2.dialogue = "YUKI: bye"
    frame, clip, spent = await runner._process_beat(
        [s1, s2], job, {"Yuki": make_char()}, BIBLE, 1,
        prev_last_frame_url=None, scene_anchor_url=None, prev_shot_type=None)
    assert (runner.qwen.generate_video_wan.await_count
            + runner.qwen.generate_video_wan_r2v.await_count
            + runner.qwen.generate_video_happyhorse.await_count) == 1
    assert len(billed) == 1
    clips = [c.args[0] for c in runner.db.add.call_args_list]
    assert len(clips) == 2
    assert clips[0].url == clips[1].url
    assert clips[0].trim_start == 0.0 and clips[1].trim_end == 10.0
    assert clips[0].trim_end == clips[1].trim_start
    assert clips[0].shot_id == "shot1" and clips[1].shot_id == "shot2"


@pytest.mark.asyncio
async def test_multishot_beat_dispatch_failure_returns_none(monkeypatch):
    # dispatch (generate_video_wan) blows up: _process_beat returns the
    # sentinel (None, None, 0.0) and writes NO clip, so the caller falls back
    # to per-shot rendering without losing the beat.
    runner = make_runner()
    runner.qwen.generate_video_wan = AsyncMock(side_effect=RuntimeError("dispatch down"))
    runner.continuity.validate = AsyncMock(return_value={
        "continuity_score": 80, "overall_pass": True,
        "face_score": 0.8, "outfit_score": 0.7, "background_score": 0.6})
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    monkeypatch.setattr(gr.get_settings(), "multishot_enabled", True, raising=False)
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=2)
    s1 = make_shot(); s1.number = 1
    s2 = make_shot(); s2.id = "shot2"; s2.number = 2
    result = await runner._process_beat(
        [s1, s2], job, {"Yuki": make_char()}, BIBLE, 1,
        prev_last_frame_url=None, scene_anchor_url=None, prev_shot_type=None)
    assert result == (None, None, 0.0)
    runner.db.add.assert_not_called()


@pytest.mark.asyncio
async def test_multishot_beat_post_dispatch_failure_is_caught(monkeypatch):
    # dispatch SUCCEEDS but a later step (poll) raises: _process_beat must
    # catch it and return clip=None instead of propagating — the _run_scene
    # fallback depends on this never-raising contract.
    runner = make_runner()
    runner.qwen.poll_video_task = AsyncMock(side_effect=RuntimeError("boom"))
    runner.continuity.validate = AsyncMock(return_value={
        "continuity_score": 80, "overall_pass": True,
        "face_score": 0.8, "outfit_score": 0.7, "background_score": 0.6})
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    monkeypatch.setattr(gr.get_settings(), "multishot_enabled", True, raising=False)
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=2)
    s1 = make_shot(); s1.number = 1
    s2 = make_shot(); s2.id = "shot2"; s2.number = 2
    result = await runner._process_beat(
        [s1, s2], job, {"Yuki": make_char()}, BIBLE, 1,
        prev_last_frame_url=None, scene_anchor_url=None, prev_shot_type=None)
    assert result[1] is None   # clip is None; did NOT raise


@pytest.mark.asyncio
async def test_continue_hold_routes_to_happyhorse_when_flagged(monkeypatch):
    runner = make_runner()
    runner.continuity.validate = _continuity_pass()
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    monkeypatch.setattr(gr.get_settings(), "identity_routing_v2", True, raising=False)
    monkeypatch.setattr(gr.get_settings(), "route_continuation_to_happyhorse", True, raising=False)
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    # prev_shot_type == this shot's CU framing so angle_changed is False -> the
    # role classifies as continue_hold (same cast, frame anchor, no angle change)
    await runner._process_shot(job, _wan_shot(), {"Yuki": make_char()}, BIBLE, 1,
                               "prevframe", prev_shot_type="CU")
    assert runner.qwen.generate_video_happyhorse.await_count == 1
    assert runner.qwen.generate_video_wan.await_count == 0


# ── wan_primary routing: HappyHorse for talk/new-face, Wan for silent visuals ──
def _hh_wan(runner):
    runner.qwen.generate_video_happyhorse = AsyncMock(return_value="hh_task")
    runner.qwen.generate_video_wan = AsyncMock(return_value="wan_task")
    runner.qwen.generate_video_wan_r2v = AsyncMock(return_value="wanr2v_task")


async def _dispatch(runner, **over):
    kw = dict(role="continue_hold", speaks=False, has_newcomers=False, has_faces=True,
              prompt="p", duration=5, seed=1, ratio="9:16", negative=None,
              ref_stack=[{"type": "reference_image", "url": "u"}],
              frame_anchor="f", prev_clip_url="c")
    kw.update(over)
    return await runner._dispatch_by_role(**kw)


@pytest.mark.asyncio
async def test_wan_primary_speaking_shot_goes_happyhorse(monkeypatch):
    monkeypatch.setattr(gr.get_settings(), "wan_primary", True, raising=False)
    r = _make_dispatch_runner(); _hh_wan(r)
    tier, _ = await _dispatch(r, role="continue_hold", speaks=True)
    assert tier == "happyhorse"
    r.qwen.generate_video_happyhorse.assert_awaited()
    r.qwen.generate_video_wan.assert_not_awaited()


@pytest.mark.asyncio
async def test_wan_primary_newcomer_goes_happyhorse(monkeypatch):
    monkeypatch.setattr(gr.get_settings(), "wan_primary", True, raising=False)
    r = _make_dispatch_runner(); _hh_wan(r)
    tier, _ = await _dispatch(r, role="entrance", speaks=False, has_newcomers=True)
    assert tier == "happyhorse"


@pytest.mark.asyncio
async def test_wan_primary_anchor_with_faces_goes_happyhorse(monkeypatch):
    monkeypatch.setattr(gr.get_settings(), "wan_primary", True, raising=False)
    r = _make_dispatch_runner(); _hh_wan(r)
    tier, _ = await _dispatch(r, role="anchor", speaks=False, has_faces=True)
    assert tier == "happyhorse"


@pytest.mark.asyncio
async def test_wan_primary_silent_continuation_goes_wan(monkeypatch):
    monkeypatch.setattr(gr.get_settings(), "wan_primary", True, raising=False)
    r = _make_dispatch_runner(); _hh_wan(r)
    tier, _ = await _dispatch(r, role="continue_hold", speaks=False, has_faces=True)
    assert tier == "wan"
    r.qwen.generate_video_wan.assert_awaited()
    r.qwen.generate_video_happyhorse.assert_not_awaited()


@pytest.mark.asyncio
async def test_wan_primary_scenery_goes_wan_t2v(monkeypatch):
    monkeypatch.setattr(gr.get_settings(), "wan_primary", True, raising=False)
    r = _make_dispatch_runner(); _hh_wan(r)
    tier, _ = await _dispatch(r, role="anchor", speaks=False, has_faces=False,
                              frame_anchor=None, prev_clip_url=None, ref_stack=None)
    assert tier == "wan"
    assert r.qwen.generate_video_wan.await_args.kwargs["reference_media"] is None


@pytest.mark.asyncio
async def test_wan_primary_wan_failure_falls_back_to_happyhorse(monkeypatch):
    monkeypatch.setattr(gr.get_settings(), "wan_primary", True, raising=False)
    r = _make_dispatch_runner(); _hh_wan(r)
    r.qwen.generate_video_wan = AsyncMock(side_effect=RuntimeError("wan down"))
    tier, _ = await _dispatch(r, role="continue_hold", speaks=False)
    assert tier == "happyhorse"


@pytest.mark.asyncio
async def test_wan_primary_off_uses_existing_routing(monkeypatch):
    monkeypatch.setattr(gr.get_settings(), "wan_primary", False, raising=False)
    monkeypatch.setattr(gr.get_settings(), "route_continuation_to_happyhorse", True, raising=False)
    r = _make_dispatch_runner(); _hh_wan(r)
    tier, _ = await _dispatch(r, role="continue_hold", speaks=True)
    assert tier == "happyhorse"
    r.qwen.generate_video_wan.assert_not_awaited()

