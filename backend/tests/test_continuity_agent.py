import pytest
from unittest.mock import AsyncMock, MagicMock
from app.mcp_tools.continuity_agent import (
    ContinuityAgent,
    combine_scores,
    calibrate_face_similarity,
)


def test_calibration_maps_arcface_scale_to_confidence():
    # wrong face (imposter cosine ~0.1) stays clearly failing
    assert calibrate_face_similarity(0.1) < 0.25
    # the standard genuine-pair threshold is a clear pass, not "35/100"
    assert calibrate_face_similarity(0.35) == 0.75
    # a clean match saturates
    assert calibrate_face_similarity(0.65) == 1.0
    assert calibrate_face_similarity(0.9) == 1.0
    assert calibrate_face_similarity(-0.2) == 0.0
    # monotonic across the whole range
    pts = [calibrate_face_similarity(x / 100) for x in range(0, 101, 5)]
    assert pts == sorted(pts)


def test_combine_scores_weights_face_highest():
    s = combine_scores(face=0.9, outfit=0.5, background=0.5)
    # face 0.5, outfit 0.25, background 0.25 -> 0.45+0.125+0.125 = 0.70 -> 70
    assert s == 70


def test_combine_scores_handles_missing_face():
    s = combine_scores(face=None, outfit=0.8, background=0.6)
    assert 0 <= s <= 100


@pytest.mark.asyncio
async def test_validate_never_recommends_retry():
    agent = ContinuityAgent.__new__(ContinuityAgent)
    agent.embedder = MagicMock()
    agent.embedder.model = MagicMock()
    agent.embedder.model.embed_all = MagicMock(return_value=[[0.5] * 512])
    agent.embedder.compare_vectors = MagicMock(return_value=0.2)
    agent._sample = MagicMock(return_value=[b"f"])
    agent.qwen = MagicMock()
    agent.qwen.chat_vision_json = AsyncMock(return_value={"outfit_score": 0.3, "background_score": 0.4, "reason": "x"})
    agent.vl_prompt = "compare"
    agent.vl_model = "qwen3-vl-plus"
    bible = {"characters": {"Mia": {"variants": [{"plate_image_url": "u", "scene_numbers": [1], "is_default": True,
                                                   "face_vector": [0.5] * 512}]}},
             "location_by_scene": {1: "loc"}}
    out = await agent.validate(clip_url="c", duration=5, characters_in_frame=["Mia"], bible=bible, scene_number=1)
    assert "retry_instruction" not in out
    assert out["overall_pass"] is False
    assert 0 <= out["continuity_score"] <= 100


@pytest.mark.asyncio
async def test_validate_excludes_foreground_from_face_scoring():
    # Rex faces camera (0.9); Mia is a foreground shoulder, face unseen. Scoring
    # Mia's face would tank the shot, so she must be skipped for face matching.
    agent = ContinuityAgent.__new__(ContinuityAgent)
    agent.embedder = MagicMock()
    agent.embedder.model = MagicMock()
    agent.embedder.model.embed_all = MagicMock(return_value=[[0.5] * 512])
    compared = []

    def compare(ref, _fv):
        compared.append(ref)
        return 0.9 if ref == "rex_vec" else 0.1

    agent.embedder.compare_vectors = compare
    agent._sample = MagicMock(return_value=[b"f"])
    agent.qwen = MagicMock()
    agent.qwen.chat_vision_json = AsyncMock(return_value={})
    agent.vl_prompt = "compare"
    agent.vl_model = "qwen3-vl-plus"
    bible = {"characters": {
        "Rex": {"variants": [{"plate_image_url": "rex", "scene_numbers": [1],
                              "is_default": True, "face_vector": "rex_vec"}]},
        "Mia": {"variants": [{"plate_image_url": "mia", "scene_numbers": [1],
                              "is_default": True, "face_vector": "mia_vec"}]},
    }, "location_by_scene": {}}

    out = await agent.validate(
        clip_url="c", duration=5, characters_in_frame=["Rex", "Mia"],
        bible=bible, scene_number=1, foreground_characters=["Mia"])
    # only Rex's vector was compared; Mia's unseen face never dragged the score
    assert compared == ["rex_vec"]
    # cosine 0.9 is far past the genuine threshold -> full confidence
    assert out["face_score"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_two_person_shot_scores_each_character_against_their_own_face():
    # both faces are in frame; the detector returns BOTH. Each character must be
    # graded on their own best match — the old largest-face-only pass compared
    # everyone against one face and capped a perfect two-shot near 50.
    agent = ContinuityAgent.__new__(ContinuityAgent)
    agent.embedder = MagicMock()
    agent.embedder.model = MagicMock()
    agent.embedder.model.embed_all = MagicMock(return_value=["rex_face", "mia_face"])

    def compare(ref, fv):
        return 0.7 if (ref, fv) in {("rex_vec", "rex_face"), ("mia_vec", "mia_face")} else 0.1

    agent.embedder.compare_vectors = compare
    agent._sample = MagicMock(return_value=[b"f"])
    agent.qwen = MagicMock()
    agent.qwen.chat_vision_json = AsyncMock(return_value={})
    agent.vl_prompt = "compare"
    agent.vl_model = "qwen3-vl-plus"
    bible = {"characters": {
        "Rex": {"variants": [{"plate_image_url": "rex", "scene_numbers": [1],
                              "is_default": True, "face_vector": "rex_vec"}]},
        "Mia": {"variants": [{"plate_image_url": "mia", "scene_numbers": [1],
                              "is_default": True, "face_vector": "mia_vec"}]},
    }, "location_by_scene": {}}

    out = await agent.validate(
        clip_url="c", duration=5, characters_in_frame=["Rex", "Mia"],
        bible=bible, scene_number=1)
    # both matched their own face at 0.7 -> saturated confidence for both
    assert out["face_score"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_identity_drift_still_reads_low():
    # the render drew the WRONG face: no detected face matches the reference.
    # Best-match scoring must NOT rescue this — the metric exists to catch it.
    agent = ContinuityAgent.__new__(ContinuityAgent)
    agent.embedder = MagicMock()
    agent.embedder.model = MagicMock()
    agent.embedder.model.embed_all = MagicMock(return_value=[["stranger"]])
    agent.embedder.compare_vectors = MagicMock(return_value=0.12)
    agent._sample = MagicMock(return_value=[b"f"])
    agent.qwen = MagicMock()
    agent.qwen.chat_vision_json = AsyncMock(return_value={})
    agent.vl_prompt = "compare"
    agent.vl_model = "qwen3-vl-plus"
    bible = {"characters": {"Rex": {"variants": [{"plate_image_url": "rex", "scene_numbers": [1],
                                                  "is_default": True, "face_vector": "rex_vec"}]}},
             "location_by_scene": {}}
    out = await agent.validate(clip_url="c", duration=5, characters_in_frame=["Rex"],
                               bible=bible, scene_number=1)
    assert out["face_score"] < 0.3
