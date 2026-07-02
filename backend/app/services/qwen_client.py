import re
import json
import asyncio
import logging
import httpx
from openai import AsyncOpenAI
from app.config import Settings, get_settings
from app.services.usage_tracker import record_usage

logger = logging.getLogger(__name__)


class QwenClient:
    def __init__(self, settings: Settings):
        self.client = AsyncOpenAI(
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
        )
        self.api_key = settings.qwen_api_key
        self.video_base_url = settings.qwen_video_base_url.rstrip("/")
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

    # ── Video generation (DashScope native async API) ──────────────
    # Endpoint: POST {video_base}/services/aigc/video-generation/video-synthesis
    #           header X-DashScope-Async: enable -> returns output.task_id
    # Poll:     GET  {video_base}/tasks/{task_id} -> output.task_status / video_url
    VIDEO_PATH = "/services/aigc/video-generation/video-synthesis"

    @staticmethod
    def _reference_media(image_url: str) -> list[dict]:
        # DashScope video-synthesis expects reference images under input.media
        # as a list of typed objects (NOT input.img_url).
        return [{"type": "reference_image", "url": image_url}]

    async def _dispatch_video(self, model: str, input_obj: dict, parameters: dict) -> str:
        payload = {"model": model, "input": input_obj, "parameters": parameters}
        async with httpx.AsyncClient() as http:
            response = await http.post(
                self.video_base_url + self.VIDEO_PATH,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable",
                },
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()["output"]["task_id"]

    async def generate_video_wan(
        self,
        prompt: str,
        duration: int = 5,
        reference_image_url: str | None = None,
        model: str | None = None,
    ) -> str:
        # wan2.7-t2v (text) or wan2.7-i2v (image-to-video when a reference image exists)
        chosen = model or ("wan2.7-i2v" if reference_image_url else "wan2.7-t2v")
        input_obj: dict = {"prompt": prompt}
        if reference_image_url:
            input_obj["media"] = self._reference_media(reference_image_url)
        params = {"resolution": "1080P", "duration": duration}
        return await self._dispatch_video(chosen, input_obj, params)

    async def generate_video_happyhorse(
        self,
        prompt: str,
        duration: int = 5,
        mode: str = "t2v",
        reference_image_url: str | None = None,
        source_video_url: str | None = None,
        edit_instruction: str | None = None,
        model: str | None = None,
    ) -> str:
        model_map = {
            "t2v": "happyhorse-1.1-t2v",
            "i2v": "happyhorse-1.1-i2v",
            "r2v": "happyhorse-1.1-r2v",          # reference-to-video (face consistency)
            "v2v": "happyhorse-1.0-video-edit",   # video editing (regen loop)
            "edit": "happyhorse-1.0-video-edit",
        }
        chosen = model or model_map.get(mode, "happyhorse-1.1-t2v")
        input_obj: dict = {"prompt": prompt}
        if reference_image_url:
            input_obj["media"] = self._reference_media(reference_image_url)
        if source_video_url:
            input_obj["media"] = [{"type": "reference_video", "url": source_video_url}]
        params = {
            "resolution": "1080P",
            "duration": duration,
            "prompt_extend": True,
            "watermark": False,
        }
        return await self._dispatch_video(chosen, input_obj, params)

    @staticmethod
    def _extract_video_url(output: dict) -> str | None:
        # DashScope returns the URL in one of a few shapes depending on model.
        if output.get("video_url"):
            return output["video_url"]
        results = output.get("results")
        if isinstance(results, dict) and results.get("video_url"):
            return results["video_url"]
        if isinstance(results, list) and results:
            first = results[0]
            if isinstance(first, dict):
                return first.get("video_url") or first.get("url")
        return None

    async def poll_video_task(self, task_id: str, timeout: int = 600, interval: int = 5) -> str:
        elapsed = 0
        async with httpx.AsyncClient() as http:
            while elapsed < timeout:
                response = await http.get(
                    f"{self.video_base_url}/tasks/{task_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10.0,
                )
                response.raise_for_status()
                output = response.json().get("output", {})
                status = output.get("task_status")
                if status == "SUCCEEDED":
                    url = self._extract_video_url(output)
                    if not url:
                        raise RuntimeError(f"Video task {task_id} succeeded but no URL in: {output}")
                    return url
                if status in ("FAILED", "CANCELED", "UNKNOWN"):
                    raise RuntimeError(f"Video task {task_id} {status}: {output.get('message', 'unknown')}")
                await asyncio.sleep(interval)
                elapsed += interval
        raise TimeoutError(f"Video task {task_id} did not complete within {timeout}s")

    # ── Image generation/editing (Production Bible plates) ─────────
    # Endpoint: POST {video_base}{path} -> header X-DashScope-Async: enable
    #           -> returns output.task_id
    # Poll:     GET  {video_base}/tasks/{task_id} -> output.task_status / results
    async def _dispatch_image(self, model: str, input_obj: dict, parameters: dict, path: str) -> str:
        payload = {"model": model, "input": input_obj, "parameters": parameters}
        async with httpx.AsyncClient() as http:
            response = await http.post(
                self.video_base_url + path,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable",
                },
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            task_id = response.json()["output"]["task_id"]
        return await self._poll_image_task(task_id)

    @staticmethod
    def _extract_image_url(output: dict) -> str | None:
        results = output.get("results")
        if isinstance(results, list) and results:
            first = results[0]
            if isinstance(first, dict):
                return first.get("url")
        return None

    async def _poll_image_task(self, task_id: str, timeout: int = 300, interval: int = 4) -> str:
        elapsed = 0
        async with httpx.AsyncClient() as http:
            while elapsed < timeout:
                response = await http.get(
                    f"{self.video_base_url}/tasks/{task_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=30.0,
                )
                response.raise_for_status()
                output = response.json().get("output", {})
                status = output.get("task_status")
                if status == "SUCCEEDED":
                    url = self._extract_image_url(output)
                    if not url:
                        raise RuntimeError(f"Image task {task_id} succeeded but no URL in: {output}")
                    return url
                if status in ("FAILED", "CANCELED", "UNKNOWN"):
                    raise RuntimeError(f"Image task {task_id} {status}: {output.get('message', 'unknown')}")
                await asyncio.sleep(interval)
                elapsed += interval
        raise TimeoutError(f"Image task {task_id} did not complete within {timeout}s")

    async def generate_image(
        self,
        prompt: str,
        negative_prompt: str | None = None,
        size: str = "1024*1024",
    ) -> str:
        s = get_settings()
        params: dict = {"size": size, "n": 1}
        if negative_prompt:
            params["negative_prompt"] = negative_prompt
        return await self._dispatch_image(s.qwen_image_model, {"prompt": prompt}, params, s.qwen_image_path)

    async def edit_image(
        self,
        prompt: str,
        base_image_url: str,
        size: str = "1024*1024",
    ) -> str:
        s = get_settings()
        input_obj = {"prompt": prompt, "base_image_url": base_image_url}
        return await self._dispatch_image(s.qwen_image_edit_model, input_obj, {"size": size, "n": 1}, s.qwen_image_path)
