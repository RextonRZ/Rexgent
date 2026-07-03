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

    class C: pass
    c = C(); c.name = "Mia"; c.costume_variants = [v]

    class L: pass
    l = L(); l.location_key = "cafe"; l.plate_image_url = "loc"; l.scene_numbers = [1]

    bible = runner._shape_bible(characters=[c], locations=[l], style_url="style")
    assert bible["characters"]["Mia"]["variants"][0]["plate_image_url"] == "u"
    assert bible["location_by_scene"][1] == "loc"
    assert bible["style_plate"] == "style"
