import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.keyframe import render_keyframe, size_for_ratio


def test_size_for_ratio():
    assert size_for_ratio("9:16") == "1080*1920"
    assert size_for_ratio("16:9") == "1920*1080"
    assert size_for_ratio(None) == "1280*1280"


def _qwen(urls):
    q = MagicMock()
    q.generate_image_with_refs = AsyncMock(side_effect=list(urls))
    return q


@pytest.mark.asyncio
async def test_verified_keyframe_returns_first_pass():
    q = _qwen(["https://x/kf1.png"])
    with patch("app.services.keyframe._face_score", new=AsyncMock(return_value=0.8)), \
         patch("app.services.keyframe._rehost", new=AsyncMock(return_value="https://oss/kf1.png")):
        url, score, attempts = await render_keyframe(
            qwen=q, prompt="p", ref_urls=["https://a/p.png"], ratio="9:16",
            face_vector=[0.1] * 512, stylized=False, threshold=0.5)
    assert url == "https://oss/kf1.png"
    assert score == 0.8
    assert attempts == 1
    assert q.generate_image_with_refs.await_count == 1


@pytest.mark.asyncio
async def test_subthreshold_rerolls_and_keeps_best():
    q = _qwen(["https://x/kf1.png", "https://x/kf2.png", "https://x/kf3.png"])
    scores = [0.3, 0.45, 0.35]
    with patch("app.services.keyframe._face_score",
               new=AsyncMock(side_effect=scores)), \
         patch("app.services.keyframe._rehost",
               new=AsyncMock(side_effect=lambda u: f"oss:{u}")):
        url, score, attempts = await render_keyframe(
            qwen=q, prompt="p", ref_urls=["r"], ratio="16:9",
            face_vector=[0.1] * 512, stylized=False, threshold=0.5)
    assert q.generate_image_with_refs.await_count == 3   # 1 + 2 rerolls
    assert attempts == 3
    assert score == 0.45                                  # best kept
    assert url == "oss:https://x/kf2.png"


@pytest.mark.asyncio
async def test_vectorless_skips_verification_single_attempt():
    q = _qwen(["https://x/kf1.png"])
    with patch("app.services.keyframe._rehost", new=AsyncMock(return_value="oss:kf")):
        url, score, attempts = await render_keyframe(
            qwen=q, prompt="p", ref_urls=["r"], ratio="9:16",
            face_vector=None, stylized=True, threshold=0.5)
    assert url == "oss:kf"
    assert score is None
    assert attempts == 1
    assert q.generate_image_with_refs.await_count == 1


@pytest.mark.asyncio
async def test_total_failure_returns_none_never_raises():
    q = MagicMock()
    q.generate_image_with_refs = AsyncMock(side_effect=RuntimeError("boom"))
    url, score, attempts = await render_keyframe(
        qwen=q, prompt="p", ref_urls=["r"], ratio="9:16",
        face_vector=None, stylized=False, threshold=0.5)
    assert url is None and score is None
    assert attempts >= 1   # the failed attempt still gets billed
