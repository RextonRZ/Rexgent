"""LLM cast audit: one call per scene reviews each shot's cast against its
action and removes characters that are only talked about, not shown. The
deterministic guards (absence regex, framing filter) catch the patterns they
know; this pass catches the semantics they can't."""
import json
from app.services.qwen_client import QwenClient
from app.services.prompt_loader import load_prompt
from app.config import get_settings


class CastAuditor:
    def __init__(self):
        self.qwen = QwenClient(get_settings())
        self.prompt_template = load_prompt("cast_audit.txt")

    async def audit(self, scene_json: dict, shots: list[dict]) -> dict[int, list[str]]:
        payload = [{"shot_number": sd.get("shot_number"),
                    "action": sd.get("action"),
                    "dialogue": sd.get("dialogue"),
                    "characters_in_frame": sd.get("characters_in_frame")}
                   for sd in (shots or []) if isinstance(sd, dict)]
        if not payload:
            return {}
        result = await self.qwen.chat_json(messages=[
            {"role": "system", "content": self.prompt_template},
            {"role": "user", "content":
                f"Scene:\n{json.dumps(scene_json, ensure_ascii=False)}\n\n"
                f"Shots:\n{json.dumps(payload, ensure_ascii=False)}"},
        ], temperature=0.1, task="cast_audit")
        out: dict[int, list[str]] = {}
        for r in (result.get("removals") if isinstance(result, dict) else []) or []:
            if not isinstance(r, dict):
                continue
            try:
                n = int(r.get("shot_number"))
            except (TypeError, ValueError):
                continue
            names = [str(x).strip() for x in (r.get("remove") or []) if str(x).strip()]
            if names:
                out[n] = names
        return out


def apply_cast_audit(shots: list, removals: dict[int, list[str]],
                     dialogue_lines: list[dict] | None = None) -> list[str]:
    """Apply audit removals in place. The dialogue speaker is never removed
    (same speaking-order pairing as the stage passes). Returns notes."""
    notes: list[str] = []
    speakers = iter([str(l.get("character") or "").strip()
                     for l in (dialogue_lines or [])])
    for sd in shots or []:
        if not isinstance(sd, dict):
            continue
        speaker = ""
        if str(sd.get("dialogue") or "").strip():
            speaker = next(speakers, "")
        rm = {str(x).strip().upper()
              for x in removals.get(sd.get("shot_number"), [])}
        rm.discard(speaker.strip().upper())
        if not rm:
            continue
        cast = [str(c) for c in (sd.get("characters_in_frame") or [])]
        keep = [c for c in cast if c.strip().upper() not in rm]
        if keep == cast:
            continue
        dropped = [c for c in cast if c not in keep]
        sd["characters_in_frame"] = keep
        keep_up = {c.strip().upper() for c in keep}
        sd["subjects"] = [s for s in (sd.get("subjects") or [])
                          if not isinstance(s, dict)
                          or str(s.get("character") or "").strip().upper() in keep_up]
        sd["foreground_characters"] = [
            c for c in (sd.get("foreground_characters") or [])
            if str(c).strip().upper() in keep_up]
        notes.append(f"shot {sd.get('shot_number')}: audit removed "
                     f"{', '.join(dropped)} (not visibly present)")
    return notes
