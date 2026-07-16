import json
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.config import get_settings


# dialogue_density is a FORMAT preference, not watchability: the dialogue
# budget caps a 30s script at ~5 short lines, so raw density can never score
# high there — auto-blocking it at the standard threshold sent every budgeted
# short drama into a rewrite loop that made it worse. Only a truly
# near-silent script blocks on this axis.
_AXIS_BLOCK_FLOOR = {"dialogue_density": 3.0}


class NarrativeJudge:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("narrative_judge.txt")

    async def evaluate(self, script_json: dict, blocking_threshold: float = 5.0,
                       target_length: int | None = None) -> dict:
        # the judge must know the format budget, or it judges a 30-second
        # piece as if length were free and calls its tightness "sparse"
        context = ""
        if target_length:
            from app.services.script_generator import plan_dialogue_budget
            context = (
                f"FORMAT CONTEXT: this episode targets {target_length} seconds of "
                f"screen time; its dialogue budget is about "
                f"{plan_dialogue_budget(target_length)} short lines. Judge "
                "dialogue_density as how much WORK those lines do (conflict, "
                "subtext, momentum), never the raw line count.\n\n")
        messages = [
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content": context + json.dumps(script_json)},
        ]
        raw = await self.qwen.chat_json(messages=messages, temperature=0.3, task="judge")
        if not isinstance(raw, dict):
            raw = {}

        scores = raw.get("scores", {})
        blocking_issues = list(raw.get("blocking_issues", []))

        for axis, score in scores.items():
            threshold = _AXIS_BLOCK_FLOOR.get(axis, blocking_threshold)
            if isinstance(score, (int, float)) and score < threshold:
                blocking_issues.append(
                    f"{axis} score ({score}) is below minimum threshold ({threshold}). Rewrite required."
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
