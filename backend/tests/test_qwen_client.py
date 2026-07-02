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
        assert input_obj["prompt"] == "a portrait"
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
