import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import app.services.generation_runner as gr
from app.services.generation_runner import GenerationRunner


@pytest.fixture(autouse=True)
def _no_ws(monkeypatch):
    """Keep tests isolated from Redis/WebSocket, OSS re-hosting, and the cost ledger."""
    monkeypatch.setattr(gr, "emit", lambda *a, **k: None)
    monkeypatch.setattr(gr, "record_video", lambda *a, **k: 0.54)
    monkeypatch.setattr(gr, "report_agent", lambda *a, **k: None)
    monkeypatch.setattr(gr, "persist_clip_url", lambda pid, hint, url: url)


def make_runner():
    runner = GenerationRunner.__new__(GenerationRunner)
    runner.db = MagicMock()
    runner.oss = MagicMock()
    runner.oss.get_project_path = MagicMock(return_value="k")
    runner.oss.upload_bytes = MagicMock(return_value="frameurl")
    runner.qwen = MagicMock()
    runner.qwen.generate_video_happyhorse = AsyncMock(return_value="task1")
    runner.qwen.generate_video_wan = AsyncMock(return_value="task1")
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
    # CU shot: identity plate + last-frame chain + style; NO location plate
    assert roles == {"identity", "prev_frame", "style"}
    ident = next(p for p in added.references_json if p["role"] == "identity")
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


# --- wan lip-sync render chain: lip-sync -> plain first-frame -> happyhorse ---

def _continuity_pass():
    return AsyncMock(return_value={
        "continuity_score": 82, "overall_pass": True,
        "face_score": 0.8, "outfit_score": 0.7, "background_score": 0.6})


def _wan_shot():
    shot = make_shot()
    shot.quality_tier = "wan"
    return shot


LINE = {"audio_url": "http://a/line.mp3", "character_name": "Yuki"}


@pytest.mark.asyncio
async def test_eligible_wan_shot_lip_syncs_to_its_own_line(monkeypatch):
    runner = make_runner()
    runner.continuity.validate = _continuity_pass()
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    monkeypatch.setattr(gr, "get_settings",
                        lambda: SimpleNamespace(lipsync_enabled=True))
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    await runner._process_shot(job, _wan_shot(), {"Yuki": make_char()}, BIBLE, 1,
                               "prevframe", lipsync_line=LINE)
    # ONE wan dispatch: continue from the frame AND drive the mouth
    assert runner.qwen.generate_video_wan.await_count == 1
    kwargs = runner.qwen.generate_video_wan.await_args.kwargs
    assert kwargs["reference_media"] == [
        {"type": "first_frame", "url": "prevframe"},
        {"type": "driving_audio", "url": "http://a/line.mp3"}]
    assert runner.qwen.generate_video_happyhorse.await_count == 0


@pytest.mark.asyncio
async def test_lipsync_dispatch_failure_falls_back_to_plain_first_frame(monkeypatch):
    runner = make_runner()
    runner.qwen.generate_video_wan = AsyncMock(
        side_effect=[RuntimeError("400 driving_audio rejected"), "task1"])
    runner.continuity.validate = _continuity_pass()
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    monkeypatch.setattr(gr, "get_settings",
                        lambda: SimpleNamespace(lipsync_enabled=True))
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    await runner._process_shot(job, _wan_shot(), {"Yuki": make_char()}, BIBLE, 1,
                               "prevframe", lipsync_line=LINE)
    # first call (lip-sync) blew up, second call retries WITHOUT driving_audio
    assert runner.qwen.generate_video_wan.await_count == 2
    second = runner.qwen.generate_video_wan.await_args_list[1].kwargs
    assert second["reference_media"] == [{"type": "first_frame", "url": "prevframe"}]
    # the chain recovered on wan — happyhorse never entered, tier stays truthful
    assert runner.qwen.generate_video_happyhorse.await_count == 0
    added = runner.db.add.call_args[0][0]
    assert added.model_used == "wan"


@pytest.mark.asyncio
async def test_wan_shot_without_frame_anchor_renders_on_happyhorse(monkeypatch):
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
    # no frame to continue from: wan never dispatches, happyhorse r2v renders
    assert runner.qwen.generate_video_wan.await_count == 0
    assert runner.qwen.generate_video_happyhorse.await_count == 1
    assert runner.qwen.generate_video_happyhorse.await_args.kwargs["mode"] == "r2v"
    # the tier that ACTUALLY rendered — clip row and cost ledger agree
    added = runner.db.add.call_args[0][0]
    assert added.model_used == "happyhorse"
    assert seen["tier"] == "happyhorse"


@pytest.mark.asyncio
async def test_lipsync_kill_switch_renders_plain_first_frame(monkeypatch):
    runner = make_runner()
    runner.continuity.validate = _continuity_pass()
    monkeypatch.setattr(gr, "extract_last_frame", lambda url: b"f")
    # settings read via the MODULE import, so this patch is the kill switch
    monkeypatch.setattr(gr, "get_settings",
                        lambda: SimpleNamespace(lipsync_enabled=False))
    job = SimpleNamespace(id="job1", project_id="p1", actual_cost=0.0, completed_shots=0, total_shots=1)
    await runner._process_shot(job, _wan_shot(), {"Yuki": make_char()}, BIBLE, 1,
                               "prevframe", lipsync_line=LINE)
    # otherwise-eligible shot: wan still continues the scene, mouth NOT driven
    assert runner.qwen.generate_video_wan.await_count == 1
    kwargs = runner.qwen.generate_video_wan.await_args.kwargs
    assert kwargs["reference_media"] == [{"type": "first_frame", "url": "prevframe"}]


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
