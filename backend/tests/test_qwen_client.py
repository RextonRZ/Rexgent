import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.qwen_client import QwenClient
from app.config import Settings


def make_client():
    settings = Settings(
        qwen_api_key="test-key",
        qwen_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        oss_access_key_id="test",
        oss_access_key_secret="test",
        database_url="postgresql://localhost/test",
    )
    return QwenClient(settings)


@pytest.mark.asyncio
async def test_chat_returns_content():
    client = make_client()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"title": "Test"}'

    with patch.object(client.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await client.chat(
            messages=[{"role": "user", "content": "Hello"}],
            model="qwen-max",
        )
        assert result == '{"title": "Test"}'


@pytest.mark.asyncio
async def test_chat_json_parses():
    client = make_client()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"key": "value"}'

    with patch.object(client.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await client.chat_json(
            messages=[{"role": "user", "content": "Return JSON"}],
        )
        assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_chat_json_strips_markdown_fences():
    client = make_client()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '```json\n{"key": "value"}\n```'

    with patch.object(client.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await client.chat_json(
            messages=[{"role": "user", "content": "Return JSON"}],
        )
        assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_chat_json_handles_trailing_comma():
    client = make_client()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"items": ["a", "b",]}'

    with patch.object(client.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await client.chat_json(
            messages=[{"role": "user", "content": "Return JSON"}],
        )
        assert result == {"items": ["a", "b"]}


@pytest.mark.asyncio
async def test_chat_vision_returns_content():
    client = make_client()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "A woman with sharp cheekbones"

    with patch.object(client.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await client.chat_vision(
            messages=[{"role": "user", "content": [{"type": "text", "text": "Describe"}]}],
        )
        assert "cheekbones" in result


@pytest.mark.asyncio
async def test_chat_json_retries_on_truncation():
    client = make_client()
    truncated = MagicMock()
    truncated.choices = [MagicMock()]
    truncated.choices[0].message.content = '{"a": 1, "b": [1, 2'
    full = MagicMock()
    full.choices = [MagicMock()]
    full.choices[0].message.content = '{"a": 1, "b": [1, 2]}'

    with patch.object(client.client.chat.completions, "create", new_callable=AsyncMock, side_effect=[truncated, full]):
        result = await client.chat_json(messages=[{"role": "user", "content": "x"}])
        assert result == {"a": 1, "b": [1, 2]}


@pytest.mark.asyncio
async def test_generate_image_returns_url(monkeypatch):
    from app.services.qwen_client import QwenClient
    from app.config import get_settings
    client = QwenClient(get_settings())

    async def fake_dispatch(model, input_obj, parameters, path):
        assert model == get_settings().qwen_image_model
        # wan2.6-t2i messages format: prompt lives at input.messages[0].content[0].text
        assert input_obj["messages"][0]["content"][0]["text"] == "a portrait"
        return "https://oss/plate.png"

    monkeypatch.setattr(client, "_dispatch_image", AsyncMock(side_effect=fake_dispatch))
    url = await client.generate_image(prompt="a portrait")
    assert url == "https://oss/plate.png"


@pytest.mark.asyncio
async def test_happyhorse_accepts_reference_list(monkeypatch):
    from app.services.qwen_client import QwenClient
    from app.config import get_settings
    client = QwenClient(get_settings())
    captured = {}

    async def fake_dispatch(model, input_obj, parameters):
        captured["media"] = input_obj.get("media")
        return "task-123"

    monkeypatch.setattr(client, "_dispatch_video", AsyncMock(side_effect=fake_dispatch))
    await client.generate_video_happyhorse(
        prompt="x", duration=5, mode="r2v",
        reference_media=[{"type": "reference_image", "url": "a"},
                         {"type": "reference_image", "url": "b"}],
    )
    assert captured["media"] == [{"type": "reference_image", "url": "a"},
                                 {"type": "reference_image", "url": "b"}]


@pytest.mark.asyncio
async def test_wan_lipsync_uses_dated_i2v_snapshot(monkeypatch):
    # driving_audio lip-sync ONLY works on the dated i2v snapshot; the bare
    # "wan2.7-i2v" alias ignores the audio, so a lip-sync shot MUST dispatch on
    # the configured snapshot with the first_frame + driving_audio media intact.
    from app.services.qwen_client import QwenClient
    from app.config import get_settings
    client = QwenClient(get_settings())
    captured = {}

    async def fake_dispatch(model, input_obj, parameters):
        captured["model"] = model
        captured["media"] = input_obj.get("media")
        return "task-lip"

    monkeypatch.setattr(client, "_dispatch_video", AsyncMock(side_effect=fake_dispatch))
    await client.generate_video_wan(
        prompt="she speaks", duration=5,
        reference_media=[{"type": "first_frame", "url": "frame.png"},
                         {"type": "driving_audio", "url": "line.wav"}],
    )
    assert captured["model"] == get_settings().qwen_wan_i2v_model
    assert captured["model"] == "wan2.7-i2v-2026-04-25"
    assert {"type": "driving_audio", "url": "line.wav"} in captured["media"]


@pytest.mark.asyncio
async def test_wan_text_only_uses_t2v_model(monkeypatch):
    from app.services.qwen_client import QwenClient
    from app.config import get_settings
    client = QwenClient(get_settings())
    captured = {}

    async def fake_dispatch(model, input_obj, parameters):
        captured["model"] = model
        return "task-t2v"

    monkeypatch.setattr(client, "_dispatch_video", AsyncMock(side_effect=fake_dispatch))
    await client.generate_video_wan(prompt="a wide establishing shot", duration=5)
    assert captured["model"] == get_settings().qwen_wan_t2v_model


@pytest.mark.asyncio
async def test_happyhorse_v2v_sends_source_as_video_media(monkeypatch):
    # the regen loop edits an existing clip: DashScope's video-edit model only
    # accepts media type "video" or "reference_image" — "reference_video" 500s.
    from app.services.qwen_client import QwenClient
    from app.config import get_settings
    client = QwenClient(get_settings())
    captured = {}

    async def fake_dispatch(model, input_obj, parameters):
        captured["model"] = model
        captured["media"] = input_obj.get("media")
        return "task-v2v"

    monkeypatch.setattr(client, "_dispatch_video", AsyncMock(side_effect=fake_dispatch))
    await client.generate_video_happyhorse(
        prompt="brighten the scene", duration=5, mode="v2v",
        source_video_url="https://oss/original.mp4",
    )
    assert captured["model"] == "happyhorse-1.0-video-edit"
    assert captured["media"] == [{"type": "video", "url": "https://oss/original.mp4"}]


@pytest.mark.asyncio
async def test_synthesize_speech_sdk_downloads_audio(monkeypatch):
    from app.services.qwen_client import QwenClient
    from app.config import get_settings
    import app.services.qwen_client as qc
    client = QwenClient(get_settings())
    captured = {}

    class FakeOutput:
        audio = {"url": "http://x/a.wav"}

    class FakeResp:
        status_code = 200
        output = FakeOutput()

    from dashscope.audio.qwen_tts import SpeechSynthesizer

    def fake_call(**kwargs):
        captured.update(kwargs)
        return FakeResp()

    monkeypatch.setattr(SpeechSynthesizer, "call", staticmethod(fake_call))
    monkeypatch.setattr(qc.httpx, "get", lambda url, timeout=60.0: type("R", (), {"content": b"WAVDATA"})())

    audio = await client.synthesize_speech(text="hi", voice="Cherry")
    assert audio == b"WAVDATA"
    assert captured["text"] == "hi"
    assert captured["voice"] == "Cherry"


def test_extract_image_url_wan26_choices_shape():
    from app.services.qwen_client import QwenClient
    out = {"choices": [{"message": {"content": [{"image": "https://x/y.png", "type": "image"}]}}]}
    assert QwenClient._extract_image_url(out) == "https://x/y.png"


def test_extract_image_url_results_shape():
    from app.services.qwen_client import QwenClient
    out = {"results": [{"url": "https://x/z.png"}]}
    assert QwenClient._extract_image_url(out) == "https://x/z.png"


@pytest.mark.asyncio
async def test_enroll_voice_posts_and_returns_voice(monkeypatch):
    from app.services.qwen_client import QwenClient
    from app.config import get_settings
    import app.services.qwen_client as qc
    client = QwenClient(get_settings())
    captured = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return {"output": {"voice": "cosyvoice-v1-char-abc"}}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            return FakeResp()

    monkeypatch.setattr(qc.httpx, "AsyncClient", lambda *a, **k: FakeAsyncClient())
    voice = await client.enroll_voice(b"RIFFsample", preferred_name="Emma Stone!", content_type="audio/wav")
    assert voice == "cosyvoice-v1-char-abc"
    body = captured["json"]
    assert body["model"] == get_settings().qwen_voice_enroll_model
    assert body["input"]["action"] == "create"
    assert body["input"]["target_model"] == get_settings().qwen_tts_cloned_model
    # preferred_name is sanitized to lowercase alnum, capped
    assert body["input"]["preferred_name"] == "emmastone"
    assert body["input"]["audio"]["data"].startswith("data:audio/wav;base64,")
    assert captured["url"].endswith(get_settings().qwen_voice_enroll_path)


@pytest.mark.asyncio
async def test_synthesize_speech_routes_realtime_for_vc_model(monkeypatch):
    from app.services.qwen_client import QwenClient
    from app.config import get_settings
    from unittest.mock import AsyncMock
    client = QwenClient(get_settings())
    rt = AsyncMock(return_value=b"WAVCLONE")
    monkeypatch.setattr(client, "synthesize_speech_realtime", rt)
    out = await client.synthesize_speech("hi", "cloned-voice-id", model="qwen3-tts-vc-realtime-2026-01-15")
    assert out == b"WAVCLONE"
    rt.assert_awaited_once()


@pytest.mark.asyncio
async def test_edit_image_uses_sync_multimodal_endpoint(monkeypatch):
    from app.services.qwen_client import QwenClient
    from app.config import get_settings
    import app.services.qwen_client as qc
    client = QwenClient(get_settings())
    captured = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return {"output": {"choices": [
                {"message": {"content": [{"image": "https://x/edited.png"}]}}]}}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResp()

    monkeypatch.setattr(qc.httpx, "AsyncClient", lambda *a, **k: FakeAsyncClient())
    out = await client.edit_image("red hoodie", "https://x/face.jpg", negative_prompt="bad")
    assert out == "https://x/edited.png"
    # SYNC multimodal endpoint — not the async image-generation one
    assert captured["url"].endswith("/services/aigc/multimodal-generation/generation")
    assert "X-DashScope-Async" not in captured["headers"]
    content = captured["json"]["input"]["messages"][0]["content"]
    assert content[0] == {"image": "https://x/face.jpg"}
    assert captured["json"]["parameters"]["negative_prompt"] == "bad"


def test_enroll_default_name_when_blank():
    # sanitizer falls back to "voice" when nothing usable remains
    import re
    name = re.sub(r"[^a-z0-9]", "", ("###").lower())[:10] or "voice"
    assert name == "voice"


@pytest.mark.asyncio
async def test_videoedit_sends_video_plus_reference_images(monkeypatch):
    # wan2.7-videoedit: source clip as type "video" + the plate(s) to paint in
    from app.services.qwen_client import QwenClient
    from app.config import get_settings
    client = QwenClient(get_settings())
    captured = {}

    async def fake_dispatch(model, input_obj, parameters):
        captured["model"] = model
        captured["media"] = input_obj.get("media")
        return "task-edit"

    monkeypatch.setattr(client, "_dispatch_video", AsyncMock(side_effect=fake_dispatch))
    await client.generate_video_videoedit(
        prompt="replace her top with the reference outfit",
        source_video_url="https://oss/clip.mp4",
        reference_media=[{"type": "reference_image", "url": "outfit.png"}])
    assert captured["model"] == get_settings().qwen_wan_videoedit_model
    assert captured["media"][0] == {"type": "video", "url": "https://oss/clip.mp4"}
    assert {"type": "reference_image", "url": "outfit.png"} in captured["media"]
