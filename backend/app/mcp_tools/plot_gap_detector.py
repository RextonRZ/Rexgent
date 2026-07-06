import json
import uuid
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.services.language import language_instruction
from app.config import get_settings


class PlotGapDetector:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("plot_gap_detect.txt")

    async def detect(self, script_json: dict, sensitivity: str = "NORMAL", language: str = "en") -> dict:
        messages = [
            {"role": "system", "content": self.prompt_template + language_instruction(language)},
            {"role": "user", "content": json.dumps(script_json, ensure_ascii=False)},
        ]
        flags_raw = await self.qwen.chat_json(messages=messages, temperature=0.2, task="plot_gap")
        # JSON mode may wrap the array in an object — unwrap it
        flags_raw = QwenClient.as_list(flags_raw)

        for flag in flags_raw:
            flag["flag_id"] = f"flag_{uuid.uuid4().hex[:8]}"
            flag["status"] = "OPEN"

        critical = sum(1 for f in flags_raw if f.get("severity") == "CRITICAL")
        major = sum(1 for f in flags_raw if f.get("severity") == "MAJOR")
        minor = sum(1 for f in flags_raw if f.get("severity") == "MINOR")

        return {
            "total_flags": len(flags_raw),
            "critical_count": critical,
            "major_count": major,
            "minor_count": minor,
            "flags": flags_raw,
        }
