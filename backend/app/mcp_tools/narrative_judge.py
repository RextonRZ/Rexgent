import json
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.config import get_settings


class NarrativeJudge:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("narrative_judge.txt")

    async def evaluate(self, script_json: dict, blocking_threshold: float = 5.0) -> dict:
        messages = [
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": json.dumps(script_json)},
        ]
        raw = await self.qwen.chat_json(messages=messages, temperature=0.3)
        if not isinstance(raw, dict):
            raw = {}

        scores = raw.get("scores", {})
        blocking_issues = list(raw.get("blocking_issues", []))

        for axis, score in scores.items():
            if isinstance(score, (int, float)) and score < blocking_threshold:
                blocking_issues.append(
                    f"{axis} score ({score}) is below minimum threshold ({blocking_threshold}). Rewrite required."
                )

        overall = raw.get("overall", 0)
        if blocking_issues:
            recommendation = "REVISE_FIRST"
        elif overall < 6.0:
            recommendation = "MAJOR_REWRITE"
        else:
            recommendation = "PROCEED"

        return {
            "scores": scores,
            "overall": overall,
            "blocking_issues": blocking_issues,
            "top_strengths": raw.get("top_strengths", []),
            "top_weaknesses": raw.get("top_weaknesses", []),
            "recommendation": recommendation,
            "judge_summary": raw.get("judge_summary", ""),
        }
