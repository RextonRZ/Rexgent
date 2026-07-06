from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.services.guardrails import InputSanitizer, PromptSanitizer
from app.config import get_settings


class RegenPromptRewriter:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("regen_prompt_rewrite.txt")

    async def rewrite(self, original_prompt: str, flag_description: str, flag_type: str) -> dict:
        clean_flag = InputSanitizer().sanitize(flag_description, max_length=500)
        user_content = (
            f"Original prompt:\n{original_prompt}\n\n"
            f"What the user said was wrong:\n{clean_flag}\n\n"
            f"Change type: {flag_type}"
        )
        messages = [
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": user_content},
        ]
        result = await self.qwen.chat_json(messages=messages, temperature=0.3, task="regen_rewrite")
        if not isinstance(result, dict):
            return {"revised_prompt": original_prompt, "changes_made": [], "confidence": 0}
        # Keep the revised prompt free of text/numbers/names too.
        result["revised_prompt"] = PromptSanitizer().sanitize(
            result.get("revised_prompt", original_prompt)
        )
        return result
