import re
import json
import asyncio
import logging
import httpx
from openai import AsyncOpenAI
from app.config import Settings
from app.services.usage_tracker import record_usage

logger = logging.getLogger(__name__)


class QwenClient:
    def __init__(self, settings: Settings):
        self.client = AsyncOpenAI(
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
        )
        self.max_retries = 3

    async def chat(
        self,
        messages: list[dict],
        model: str = "qwen-max",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                record_usage(getattr(response, "usage", None))
                return response.choices[0].message.content
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                wait = 2 ** attempt
                logger.warning(f"Qwen chat attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                await asyncio.sleep(wait)

    async def chat_json(
        self,
        messages: list[dict],
        model: str = "qwen-max",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict | list:
        # Truncation guard: if the response is cut off, retry once with more tokens.
        content = await self.chat(messages, model, temperature, max_tokens)
        if self._looks_truncated(content):
            logger.warning("Truncated JSON response — retrying with larger max_tokens")
            content = await self.chat(messages, model, temperature, max_tokens * 2)
        return self._parse_json(content)

    @staticmethod
    def _looks_truncated(raw: str) -> bool:
        if not raw:
            return False
        s = raw.strip()
        return (s.count("{") - s.count("}") > 0) or (s.count("[") - s.count("]") > 0)

    async def chat_vision(
        self,
        messages: list[dict],
        model: str = "qwen-vl-max",
        max_tokens: int = 2048,
    ) -> str:
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                )
                record_usage(getattr(response, "usage", None))
                return response.choices[0].message.content
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                wait = 2 ** attempt
                logger.warning(f"Qwen VL attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                await asyncio.sleep(wait)

    @staticmethod
    def _parse_json(content: str) -> dict | list:
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        cleaned = re.sub(r',\s*}', '}', cleaned)
        cleaned = re.sub(r',\s*]', ']', cleaned)
        return json.loads(cleaned)

    async def chat_vision_json(
        self,
        messages: list[dict],
        model: str = "qwen-vl-max",
        max_tokens: int = 2048,
    ) -> dict | list:
        content = await self.chat_vision(messages, model, max_tokens)
        return self._parse_json(content)

    # NOTE: Video endpoints are built from the OpenAI-compatible base URL.
    # When real Qwen Cloud keys are available (File 14 testing), confirm the
    # actual Wan/HappyHorse async endpoint paths and model IDs against the
    # DashScope docs and adjust the URL/payload here if needed.
    async def generate_video_wan(
        self,
        prompt: str,
        duration: int = 5,
        reference_image_url: str | None = None,
        first_frame_url: str | None = None,
        last_frame_url: str | None = None,
    ) -> str:
        payload = {
            "model": "wan2.1-t2v-plus",
            "input": {
                "prompt": prompt,
                "duration": duration,
                "resolution": "1080p",
            },
        }
        if reference_image_url:
            payload["input"]["reference_images"] = [reference_image_url]
        if first_frame_url:
            payload["input"]["first_frame"] = first_frame_url
        if last_frame_url:
            payload["input"]["last_frame"] = last_frame_url

        async with httpx.AsyncClient() as http:
            response = await http.post(
                f"{self.client.base_url}".rstrip("/") + "/services/aigc/video-generation/generation",
                headers={
                    "Authorization": f"Bearer {self.client.api_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable",
                },
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()["output"]["task_id"]

    async def generate_video_happyhorse(
        self,
        prompt: str,
        duration: int = 5,
        mode: str = "t2v",
        reference_image_url: str | None = None,
        source_video_url: str | None = None,
        edit_instruction: str | None = None,
    ) -> str:
        model_map = {
            "t2v": "happyhorse-1.1-t2v",
            "i2v": "happyhorse-1.1-i2v",
            "s2v": "happyhorse-1.1-s2v",
            "v2v": "happyhorse-1.1-v2v",
        }
        payload = {
            "model": model_map.get(mode, f"happyhorse-1.1-{mode}"),
            "input": {
                "prompt": prompt,
                "duration": duration,
                "resolution": "1080p",
                "audio_mode": "auto",
            },
        }
        if reference_image_url:
            payload["input"]["subject_image"] = reference_image_url
        if source_video_url:
            payload["input"]["source_video"] = source_video_url
        if edit_instruction:
            payload["input"]["edit_instruction"] = edit_instruction

        async with httpx.AsyncClient() as http:
            response = await http.post(
                f"{self.client.base_url}".rstrip("/") + "/services/aigc/video-generation/generation",
                headers={
                    "Authorization": f"Bearer {self.client.api_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable",
                },
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()["output"]["task_id"]

    async def poll_video_task(self, task_id: str, timeout: int = 300, interval: int = 5) -> str:
        elapsed = 0
        async with httpx.AsyncClient() as http:
            while elapsed < timeout:
                response = await http.get(
                    f"{self.client.base_url}".rstrip("/") + f"/tasks/{task_id}",
                    headers={"Authorization": f"Bearer {self.client.api_key}"},
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()
                status = data["output"]["task_status"]
                if status == "SUCCEEDED":
                    return data["output"]["results"][0]["url"]
                if status == "FAILED":
                    raise RuntimeError(f"Video task {task_id} failed: {data['output'].get('message', 'unknown')}")
                await asyncio.sleep(interval)
                elapsed += interval
        raise TimeoutError(f"Video task {task_id} did not complete within {timeout}s")
