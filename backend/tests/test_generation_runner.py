import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from app.services.generation_runner import GenerationRunner


def make_runner():
    runner = GenerationRunner.__new__(GenerationRunner)
    runner.db = MagicMock()
    runner.qwen = MagicMock()
    runner.qwen.generate_video_happyhorse = AsyncMock(return_value="task1")
    runner.qwen.generate_video_wan = AsyncMock(return_value="task1")
    runner.qwen.poll_video_task = AsyncMock(return_value="http://x/clip.mp4")
    runner.prompt_crafter = MagicMock()
    runner.prompt_crafter.craft = AsyncMock(return_value={"prompt": "base prompt"})
    runner.consistency_guard = MagicMock()
    runner.budget_ceiling = 34.0
    return runner


def make_shot():
    return SimpleNamespace(
        id="shot1", shot_type="CU", camera_movement="STATIC", action="x",
        lighting="NATURAL", colour_mood="COOL", emotional_beat="tension",
        estimated_duration_seconds=5, quality_tier="happyhorse",
        characters_in_frame=["Yuki"],
    )


def make_char():
    return SimpleNamespace(
        name="Yuki", face_vector=[0.1] * 512, video_prompt_fragment="young detective",
        visual_description="young detective", face_embedding={"embedding_keywords": ["sharp cheekbones"]},
    )


@pytest.mark.asyncio
async def test_passing_clip_is_approved():
    runner = make_runner()
    runner.consistency_guard.validate = AsyncMock(return_value={
        "overall_pass": True, "overall_similarity": 0.9, "retry_instruction": None,
    })
    job = SimpleNamespace(id="job1", actual_cost=0.0, completed_shots=0)

    await runner._process_shot(job, make_shot(), {"Yuki": make_char()})

    added = runner.db.add.call_args[0][0]
    assert added.status == "APPROVED"
    assert job.completed_shots == 1


@pytest.mark.asyncio
async def test_smart_retry_applies_diagnosis_then_passes():
    runner = make_runner()
    runner.consistency_guard.validate = AsyncMock(side_effect=[
        {"overall_pass": False, "overall_similarity": 0.3, "retry_instruction": "use short black hair"},
        {"overall_pass": True, "overall_similarity": 0.85, "retry_instruction": None},
    ])
    job = SimpleNamespace(id="job1", actual_cost=0.0, completed_shots=0)

    await runner._process_shot(job, make_shot(), {"Yuki": make_char()})

    # Second generation call should carry the diagnosis instruction.
    second_prompt = runner.qwen.generate_video_happyhorse.call_args_list[1].kwargs["prompt"]
    assert "use short black hair" in second_prompt
    final_clip = runner.db.add.call_args[0][0]
    assert final_clip.status == "APPROVED"
    assert final_clip.retries == 1


@pytest.mark.asyncio
async def test_exhausted_retries_needs_review():
    runner = make_runner()
    runner.consistency_guard.validate = AsyncMock(return_value={
        "overall_pass": False, "overall_similarity": 0.2, "retry_instruction": "brighten",
    })
    job = SimpleNamespace(id="job1", actual_cost=0.0, completed_shots=0)

    await runner._process_shot(job, make_shot(), {"Yuki": make_char()})

    final_clip = runner.db.add.call_args[0][0]
    assert final_clip.status == "NEEDS_REVIEW"
    assert job.completed_shots == 1
