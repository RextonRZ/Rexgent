import asyncio
import logging
from app.services.qwen_client import QwenClient
from app.services.oss_manager import OSSManager
from app.config import get_settings
from app.websocket.emitter import emit

logger = logging.getLogger(__name__)

# A single flaky TTS call must not silently drop a line for the whole export:
# on the deployed box (the user's own key, under load) a transient error would
# lose that line's voice AND its caption forever, since captions follow the
# placed voices. Retry each line a few times before giving up.
TTS_LINE_ATTEMPTS = 3


def line_direction(line: dict) -> str | None:
    """The acting notes for one line: the parenthetical the writer embedded
    ("(whispering, frantic)") plus any explicit direction field (the shot's
    emotional beat rides in on it) — stripped from the SPOKEN text, but
    handed to the instruct TTS so the delivery matches the writing."""
    import re
    bits = re.findall(r"\(([^)]+)\)", line.get("line") or "")
    if line.get("direction"):
        bits.append(str(line["direction"]))
    joined = ", ".join(b.strip() for b in bits if b.strip())
    return joined or None


def scene_line_beats(shots: list[dict]) -> list[str | None]:
    """A scene's emotional beats in speaking order: the k-th dialogue line
    pairs with the k-th dialogue-bearing shot (the SAME order-based convention
    placement uses), so beats[k] is the acting direction for line k."""
    speaking = sorted((s for s in shots or []
                       if str(s.get("dialogue") or "").strip()),
                      key=lambda s: s.get("number") or 0)
    return [s.get("emotional_beat") for s in speaking]


def probe_duration(audio_bytes: bytes) -> float:
    import tempfile, subprocess, os
    p = tempfile.mktemp(suffix=".wav")
    with open(p, "wb") as f:
        f.write(audio_bytes)
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=nw=1:nk=1", p], capture_output=True, text=True)
        return float(out.stdout.strip() or 0.0)
    except Exception:  # noqa: BLE001
        return 0.0
    finally:
        try:
            os.unlink(p)
        except OSError:
            pass


class DialogueSynthesizer:
    def __init__(self, db=None):
        s = get_settings()
        self.qwen = QwenClient(s)
        self.oss = OSSManager(s)
        self.db = db

    async def synthesize_lines(self, project_id, scenes, voice_by_name,
                               only_characters=None) -> list[dict]:
        """Synthesize dialogue lines. only_characters (a set of names) restricts
        synthesis to those speakers — used when a voice was recast after the
        first synthesis. line_index always comes from the FULL dialogue list so
        timeline placement stays stable across partial re-runs."""
        pid = str(project_id)

        def _want(line) -> bool:
            return only_characters is None or line.get("character") in only_characters

        _direction = line_direction

        def _spoken(text) -> str:
            """Strip parenthetical stage directions: '(whispering, frantic)
            Mom, please' must be ACTED, not read aloud - and the direction
            leaks into captions too, since they render this same text."""
            import re
            cleaned = re.sub(r"\([^)]*\)", " ", text or "")
            cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
            return cleaned or (text or "")

        total = sum(1 for s in scenes for line in (s.get("dialogue_json") or []) if _want(line))
        idx, rows = 0, []
        for scene in scenes:
            for li, line in enumerate(scene.get("dialogue_json") or []):
                if not _want(line):
                    continue
                idx += 1
                name = line.get("character")
                # "CATHERINE (V.O.)" must speak with CATHERINE's voice — stage
                # qualifiers resolve to the cast member, same as everywhere else
                from app.services.guardrails import canonical_character
                voice = (voice_by_name.get(name)
                         or voice_by_name.get(canonical_character(name or "", voice_by_name))
                         or {})
                vid = voice.get("voice_id") or "Cherry"  # preset fallback for unknown speakers
                emit("audio.tts.started", {"scene_number": scene["number"], "line_index": li,
                                           "index": idx, "total": total}, pid)
                # One flaky line (the cloned-voice websocket especially) must
                # not sink the whole batch: retry the line a few times, keep
                # every line that succeeded, skip a line that fails every
                # attempt, and let the export's missing-line detection retry it.
                audio, last_err = None, None
                for attempt in range(TTS_LINE_ATTEMPTS):
                    try:
                        audio = await self.qwen.synthesize_speech(
                            _spoken(line.get("line", "")), vid, voice.get("voice_model"),
                            instructions=_direction(line))
                        break
                    except Exception as e:  # noqa: BLE001
                        last_err = e
                        if attempt < TTS_LINE_ATTEMPTS - 1:
                            await asyncio.sleep(0.6 * (attempt + 1))
                if audio is None:
                    logger.warning(
                        f"TTS failed for {name} (voice {vid}) s{scene['number']}l{li} "
                        f"after {TTS_LINE_ATTEMPTS} attempts: {last_err}")
                    emit("audio.tts.failed", {"scene_number": scene["number"], "line_index": li,
                                              "character": name, "error": str(last_err)[:200]}, pid)
                    continue
                key = self.oss.get_project_path(pid, "audio", f"s{scene['number']}_l{li}.wav")
                url = self.oss.upload_bytes(audio, key, content_type="audio/wav")
                rows.append({"project_id": project_id, "scene_number": scene["number"], "line_index": li,
                             "character_name": name, "text": _spoken(line.get("line", "")), "voice_id": vid,
                             "audio_url": url, "duration_seconds": probe_duration(audio)})
                if getattr(self, "db", None) is not None:
                    from app.services.cost_ledger import record_tts
                    vm = (voice.get("voice_model") or "").lower()
                    record_tts(self.db, project_id, len(line.get("line", "")),
                               model=("qwen3-tts-vc-realtime" if "realtime" in vm
                                      else vm if "tts-vd" in vm
                                      else "qwen3-tts-flash"))
                emit("audio.tts.completed", {"scene_number": scene["number"], "line_index": li,
                                             "index": idx, "total": total}, pid)
        return rows
