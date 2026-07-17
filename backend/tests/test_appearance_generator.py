import pytest
from app.services.appearance_generator import AppearanceGenerator


@pytest.mark.asyncio
async def test_appearance_generate_carries_age_and_gender():
    # the autofill invented a late-twenties man for a 12-year-old boy because
    # it never received the age — now age and gender ride into the request
    ag = AppearanceGenerator.__new__(AppearanceGenerator)
    ag.prompt_template = "sys"
    captured = {}

    class FakeQwen:
        async def chat_json(self, messages, **kw):
            captured["user"] = messages[1]["content"]
            return {"video_prompt_fragment": "ok"}

    ag.qwen = FakeQwen()
    await ag.generate(character_name="John", role="ANTAGONIST",
                      personality="nervous", physical_desc="a boy",
                      age="12", gender="male")
    assert "Age: 12" in captured["user"]
    assert "Gender: male" in captured["user"]
