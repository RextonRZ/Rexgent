import re
import json
import base64
import asyncio
import logging
import httpx
from openai import AsyncOpenAI
from app.config import Settings, get_settings
from app.services.model_router import resolve_model
from app.services.usage_tracker import record_usage

logger = logging.getLogger(__name__)


class QwenClient:
    def __init__(self, settings: Settings):
        # bring-your-own-key: the request's user (or the project's owner in a
        # worker) supplies the credential; the .env key is only the fallback
        from app.services.api_keys import resolve_qwen_key
        key = resolve_qwen_key(settings)
        self.client = AsyncOpenAI(
            api_key=key,
            base_url=settings.qwen_base_url,
            # the SDK default is 600s per attempt PLUS retries — one dropped
            # connection froze a boarding job for many minutes with no error.
            # 180s covers the longest legitimate call (a full screenplay);
            # everything else fails fast and visibly instead of hanging.
            timeout=180.0,
            max_retries=1,
        )
        self.api_key = key
        self.video_base_url = settings.qwen_video_base_url.rstrip("/")
        self.max_retries = 3

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        task: str | None = None,
        json_mode: bool = False,
    ) -> str:
        # No explicit model -> the router picks the cheapest tier the task
        # allows (creative work stays on qwen-max; structuring runs on flash).
        resolved = resolve_model(task, model)
        use_json = json_mode
        for attempt in range(self.max_retries):
            try:
                kwargs: dict = dict(
                    model=resolved,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if use_json:
                    kwargs["response_format"] = {"type": "json_object"}
                response = await self.client.chat.completions.create(**kwargs)
                record_usage(getattr(response, "usage", None), model=resolved, task=task)
                return response.choices[0].message.content
            except Exception as e:
                if use_json:
                    # Some models/prompts reject response_format — fall back to
                    # prompt-level JSON discipline rather than failing the call.
                    use_json = False
                    logger.warning(f"JSON mode rejected ({e}); retrying without response_format")
                    continue
                if attempt == self.max_retries - 1:
                    raise
                wait = 2 ** attempt
                logger.warning(f"Qwen chat attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                await asyncio.sleep(wait)

    async def chat_json(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        task: str | None = None,
    ) -> dict | list:
        # Truncation guard: if the response is cut off, retry once with more tokens.
        content = await self.chat(messages, model, temperature, max_tokens,
                                  task=task, json_mode=True)
        if self._looks_truncated(content):
            logger.warning("Truncated JSON response — retrying with larger max_tokens")
            content = await self.chat(messages, model, temperature, max_tokens * 2,
                                      task=task, json_mode=True)
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
        task: str | None = None,
    ) -> str:
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                )
                record_usage(getattr(response, "usage", None), model=model, task=task)
                return response.choices[0].message.content
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                wait = 2 ** attempt
                logger.warning(f"Qwen VL attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                await asyncio.sleep(wait)

    @staticmethod
    def as_list(result) -> list:
        """Native JSON mode guarantees an OBJECT, so a list-shaped answer often
        comes back wrapped ({"relationships": [...]}). Unwrap the first list
        value; pass real lists through; anything else is an empty list."""
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            for value in result.values():
                if isinstance(value, list):
                    return value
        return []

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
        task: str | None = None,
    ) -> dict | list:
        content = await self.chat_vision(messages, model, max_tokens, task=task)
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
        async def _submit(inp: dict) -> httpx.Response:
            payload = {"model": model, "input": inp, "parameters": parameters}
            async with httpx.AsyncClient() as http:
                return await http.post(
                    self.video_base_url + self.VIDEO_PATH,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "X-DashScope-Async": "enable",
                    },
                    json=payload,
                    timeout=30.0,
                )

        response = await _submit(input_obj)
        # negative_prompt support varies by model family; a schema rejection
        # must degrade to a plain submit, never fail the shot
        if response.status_code == 400 and "negative_prompt" in input_obj:
            logger.warning("%s rejected the submit (%s) - retrying without "
                           "negative_prompt", model, response.text[:200])
            response = await _submit({k: v for k, v in input_obj.items()
                                      if k != "negative_prompt"})
        response.raise_for_status()
        return response.json()["output"]["task_id"]

    async def generate_video_wan(
        self,
        prompt: str,
        duration: int = 5,
        reference_image_url: str | None = None,
        reference_media: list[dict] | None = None,
        model: str | None = None,
        seed: int | None = None,
        ratio: str | None = None,
        negative_prompt: str | None = None,
    ) -> str:
        # wan2.7-t2v (text) or wan2.7-i2v (image-to-video when a reference image exists)
        chosen = model or ("wan2.7-i2v" if (reference_media or reference_image_url) else "wan2.7-t2v")
        input_obj: dict = {"prompt": prompt}
        if negative_prompt:
            input_obj["negative_prompt"] = negative_prompt[:500]
        if reference_media:
            input_obj["media"] = reference_media
        elif reference_image_url:
            input_obj["media"] = self._reference_media(reference_image_url)
        params: dict = {"resolution": "1080P", "duration": duration}
        if seed is not None:
            params["seed"] = seed
        if ratio:
            # "9:16" renders true portrait (1080*1920 at 1080P) — see the
            # wan2.7 API reference; prompt text alone can't change aspect.
            params["ratio"] = ratio
        return await self._dispatch_video(chosen, input_obj, params)

    async def generate_video_wan_r2v(
        self,
        prompt: str,
        duration: int = 5,
        reference_media: list[dict] | None = None,
        seed: int | None = None,
        ratio: str | None = None,
        negative_prompt: str | None = None,
    ) -> str:
        """wan2.7-r2v: the one Wan that takes identity references (up to 5
        mixed image/video inputs) — premium quality WITH the bible's face
        plates, for shots the frame-continuation Wan cannot do."""
        s = get_settings()
        input_obj: dict = {"prompt": prompt}
        if negative_prompt:
            input_obj["negative_prompt"] = negative_prompt[:500]
        if reference_media:
            input_obj["media"] = reference_media[:5]
        params: dict = {"resolution": "1080P", "duration": duration}
        if seed is not None:
            params["seed"] = seed
        if ratio:
            params["ratio"] = ratio
        return await self._dispatch_video(s.qwen_wan_r2v_model, input_obj, params)

    async def generate_video_happyhorse(
        self,
        prompt: str,
        duration: int = 5,
        mode: str = "t2v",
        reference_image_url: str | None = None,
        reference_media: list[dict] | None = None,
        source_video_url: str | None = None,
        edit_instruction: str | None = None,
        model: str | None = None,
        seed: int | None = None,
        ratio: str | None = None,
        negative_prompt: str | None = None,
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
        if negative_prompt:
            input_obj["negative_prompt"] = negative_prompt[:500]
        if reference_media:
            input_obj["media"] = reference_media
        elif reference_image_url:
            input_obj["media"] = self._reference_media(reference_image_url)
        if source_video_url:
            # the video-edit model takes the source clip as type "video";
            # "reference_image" is the only other accepted media type here.
            input_obj["media"] = [{"type": "video", "url": source_video_url}]
        params: dict = {
            "resolution": "1080P",
            "duration": duration,
            "prompt_extend": True,
            "watermark": False,
        }
        if seed is not None:
            params["seed"] = seed
        if ratio:
            params["ratio"] = ratio
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
            if response.status_code >= 400:
                # Surface DashScope's actual error (model-not-found, bad param, etc.)
                # instead of an opaque "400 Bad Request".
                raise RuntimeError(
                    f"DashScope image-synthesis {response.status_code} "
                    f"for model '{model}': {response.text[:600]}"
                )
            task_id = response.json()["output"]["task_id"]
        return await self._poll_image_task(task_id)

    @staticmethod
    def _extract_image_url(output: dict) -> str | None:
        # Shape A — wan2.6-t2i (messages format): choices[].message.content[].image
        choices = output.get("choices")
        if isinstance(choices, list) and choices:
            content = ((choices[0] or {}).get("message", {}) or {}).get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("image"):
                        return item["image"]
        # Shape B — text2image/image-synthesis: results[].url
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
        size: str = "1280*1280",
        prompt_extend: bool = True,
    ) -> str:
        s = get_settings()
        # wan2.6-t2i: prompt goes in a messages array; size/n/negative_prompt/flags in parameters.
        input_obj: dict = {"messages": [{"role": "user", "content": [{"text": prompt}]}]}
        params: dict = {"size": size, "n": 1, "prompt_extend": prompt_extend, "watermark": False}
        if negative_prompt:
            params["negative_prompt"] = negative_prompt
        return await self._dispatch_image(s.qwen_image_model, input_obj, params, s.qwen_image_path)

    async def edit_image(
        self,
        prompt: str,
        base_image_url: str,
        negative_prompt: str | None = None,
        prompt_extend: bool = True,  # unused by the edit endpoint; kept for call-site compat
    ) -> str:
        # qwen-image-edit-max is served by the SYNCHRONOUS multimodal endpoint: the
        # async image-generation endpoint 400s with InvalidParameter "url error".
        # The edited image comes back directly in choices[0].message.content[].image
        # (verified live: reference face + outfit change preserved the person).
        s = get_settings()
        payload = {
            "model": s.qwen_image_edit_model,
            "input": {"messages": [{"role": "user", "content": [
                {"image": base_image_url}, {"text": prompt}]}]},
            "parameters": {"watermark": False,
                           **({"negative_prompt": negative_prompt} if negative_prompt else {})},
        }
        async with httpx.AsyncClient() as http:
            response = await http.post(
                self.video_base_url + s.qwen_image_edit_path,
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json"},
                json=payload,
                timeout=180.0,
            )
            if response.status_code >= 400:
                raise RuntimeError(
                    f"DashScope image-edit {response.status_code} for model "
                    f"'{s.qwen_image_edit_model}': {response.text[:600]}")
            output = response.json().get("output", {})
        url = self._extract_image_url(output)
        if not url:
            raise RuntimeError(f"Image edit returned no URL: {output}")
        return url

    async def check_face_reference(self, image_url: str) -> str:
        """Preflight a face reference against the edit model's content
        inspection AT UPLOAD TIME — before any casting money. DashScope
        rejects recognizable public figures (deep-synthesis rules) with an
        instant, unbilled DataInspectionFailed; catching it here warns the
        user the moment they pick the photo instead of after a full cast run
        quietly ships an invented stranger. A photo that passes costs one
        small edit (the probe render), which the caller ledgers.

        Returns "rejected" | "ok" | "unknown" (probe errored — don't block)."""
        try:
            await self.edit_image(
                "same person, neutral studio headshot, plain background",
                image_url, prompt_extend=False)
            return "ok"
        except Exception as e:  # noqa: BLE001
            if "DataInspectionFailed" in str(e):
                return "rejected"
            logger.warning(f"face reference preflight inconclusive: {e}")
            return "unknown"

    # ── Voice design / enrollment / TTS synthesis ───────────────────
    # DashScope's exact voice/TTS request shapes are uncertain, so these are
    # best-effort behind this interface: only this file changes if the real
    # API differs.
    async def synthesize_speech(self, text: str, voice: str, model: str | None = None,
                                instructions: str | None = None) -> bytes:
        """TTS synthesis. Preset voices use the OFFLINE SDK (qwen3-tts-flash); cloned
        voices route to the realtime vc WebSocket (any model containing 'realtime').
        `instructions` (stage directions like "whispering, tearful") route preset
        voices to the INSTRUCT model, which delivers the line accordingly —
        cloned voices have no instruct support and ignore it.
        `voice` is a preset timbre name or an enrolled voice id. Returns WAV bytes."""
        s = get_settings()
        model = model or s.qwen_tts_designed_model
        if "realtime" in model:
            return await self.synthesize_speech_realtime(text, voice, model)

        api_key, base = self.api_key, self.video_base_url

        use_instruct = bool(instructions) and model == s.qwen_tts_designed_model

        def _call() -> bytes:
            if use_instruct:
                # the instruct fields live in `input` NEXT TO text/voice, and
                # optimize_instructions is the activator — the installed SDK
                # drops both, so this goes over raw HTTP (verified live: a
                # pause-heavy instruction stretched the read 1.7s -> 2.7s)
                body = {"model": s.qwen_tts_instruct_model,
                        "input": {"text": text, "voice": voice,
                                  "instructions": instructions[:200],
                                  "optimize_instructions": True},
                        "parameters": {}}
                r = httpx.post(
                    base + "/services/aigc/multimodal-generation/generation",
                    json=body, timeout=120.0,
                    headers={"Authorization": f"Bearer {api_key}"})
                j = r.json()
                if r.status_code != 200:
                    raise RuntimeError(f"instruct TTS {r.status_code}: {str(j.get('message'))[:200]}")
                url = (j.get("output") or {}).get("audio", {}).get("url")
                if url:
                    return httpx.get(url, timeout=60.0).content
                data = (j.get("output") or {}).get("audio", {}).get("data")
                if data:
                    return base64.b64decode(data)
                raise RuntimeError("instruct TTS returned no audio")
            import dashscope
            from dashscope.audio.qwen_tts import SpeechSynthesizer
            dashscope.base_http_api_url = base  # international endpoint
            resp = SpeechSynthesizer.call(model=model, api_key=api_key, text=text, voice=voice)
            if getattr(resp, "status_code", 200) != 200:
                raise RuntimeError(
                    f"TTS {getattr(resp, 'status_code', '?')}: {getattr(resp, 'message', '')}")
            audio = resp.output.audio
            url = audio.get("url") if isinstance(audio, dict) else getattr(audio, "url", None)
            if url:
                return httpx.get(url, timeout=60.0).content
            data = audio.get("data") if isinstance(audio, dict) else getattr(audio, "data", None)
            if data:
                return base64.b64decode(data)
            raise RuntimeError(f"TTS returned no audio: {resp.output}")

        return await asyncio.to_thread(_call)

    async def enroll_voice(self, sample_bytes: bytes, preferred_name: str,
                           content_type: str = "audio/wav") -> str:
        """Enrol a custom voice from a short sample via qwen-voice-enrollment.
        Returns the enrolled voice id, usable with the qwen3-tts-vc-realtime model."""
        s = get_settings()
        name = re.sub(r"[^a-z0-9]", "", (preferred_name or "").lower())[:10] or "voice"
        b64 = base64.b64encode(sample_bytes).decode()
        payload = {
            "model": s.qwen_voice_enroll_model,
            "input": {
                "action": "create",
                "target_model": s.qwen_tts_cloned_model,
                "preferred_name": name,
                "audio": {"data": f"data:{content_type};base64,{b64}"},
            },
        }
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                self.video_base_url + s.qwen_voice_enroll_path,
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json"},
                json=payload,
                timeout=60.0,
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"Voice enrollment {resp.status_code}: {resp.text[:600]}")
            output = resp.json().get("output", {})
        voice = output.get("voice")
        if not voice:
            raise RuntimeError(f"Voice enrollment returned no voice: {output}")
        return voice

    async def synthesize_speech_realtime(self, text: str, voice: str,
                                         model: str | None = None) -> bytes:
        """TTS via the realtime vc WebSocket (qwen3-tts-vc-realtime). Accumulates the
        base64 PCM deltas and wraps them into a 24kHz mono 16-bit WAV. Blocking SDK,
        so it runs in a worker thread."""
        s = get_settings()
        model = model or s.qwen_tts_cloned_model
        api_key, ws_url = self.api_key, s.qwen_tts_realtime_url

        def _call() -> bytes:
            import io
            import wave
            import threading
            import dashscope
            from dashscope.audio.qwen_tts_realtime import (
                QwenTtsRealtime, QwenTtsRealtimeCallback, AudioFormat)

            dashscope.api_key = api_key  # QwenTtsRealtime reads api_key at construction
            chunks: list[bytes] = []
            done = threading.Event()
            error: dict = {}

            class _CB(QwenTtsRealtimeCallback):
                def on_open(self) -> None:
                    pass

                def on_close(self, close_status_code, close_msg) -> None:
                    done.set()

                def on_event(self, message: dict) -> None:
                    try:
                        etype = message.get("type")
                        if etype == "response.audio.delta":
                            b64 = message.get("delta") or message.get("audio")
                            if b64:
                                chunks.append(base64.b64decode(b64))
                        elif etype in ("response.done", "session.finished"):
                            done.set()
                        elif etype == "error":
                            error["msg"] = message.get("error") or message
                            done.set()
                    except Exception as e:  # noqa: BLE001
                        error["msg"] = str(e)
                        done.set()

            tts = QwenTtsRealtime(model=model, callback=_CB(), url=ws_url)
            tts.connect()
            tts.update_session(voice=voice,
                               response_format=AudioFormat.PCM_24000HZ_MONO_16BIT)
            tts.append_text(text)
            tts.finish()
            done.wait(timeout=90)
            try:
                tts.close()
            except Exception:  # noqa: BLE001
                pass
            if error:
                raise RuntimeError(f"Realtime TTS error: {error['msg']}")
            pcm = b"".join(chunks)
            if not pcm:
                raise RuntimeError("Realtime TTS returned no audio")
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(pcm)
            return buf.getvalue()

        return await asyncio.to_thread(_call)

    async def preview_voice(self, text: str, voice: str, model: str | None = None) -> bytes:
        # Preset voices preview through flash; cloned voices pass their realtime model.
        return await self.synthesize_speech(text, voice, model or get_settings().qwen_tts_preview_model)
