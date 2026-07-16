"""Ground-truth frame handoff: a VL model reads the ACTUAL final frame of the
previous clip — who is where, seated or standing, holding what, door open or
closed — so the next shot's prompt opens from what really rendered instead of
what the storyboard hoped had rendered. This replaces the removed prev-frame
image reference (which duplicated people) with a textual handoff that cannot."""
import logging

from app.config import get_settings
from app.services.prompt_loader import load_prompt
from app.services.qwen_client import QwenClient

logger = logging.getLogger(__name__)


class FrameReader:
    def __init__(self):
        s = get_settings()
        self.qwen = QwenClient(s)
        self.model = s.qwen_vl_continuity_model
        self.prompt = load_prompt("frame_describe.txt")

    async def describe(self, image_url: str) -> str | None:
        """One VL call: a 2-4 sentence visual inventory of the frame, or None
        on any failure — the caller falls back to board-text continuity."""
        if not image_url:
            return None
        try:
            content = [{"type": "image_url", "image_url": {"url": image_url}},
                       {"type": "text", "text": self.prompt}]
            out = await self.qwen.chat_vision_json(
                messages=[{"role": "user", "content": content}],
                model=self.model, task="frame_handoff")
            desc = (out or {}).get("description") if isinstance(out, dict) else None
            desc = str(desc or "").strip()
            return desc[:600] or None
        except Exception as e:  # noqa: BLE001 — handoff is an enhancement, never a blocker
            logger.warning("frame handoff read failed: %s", e)
            return None
