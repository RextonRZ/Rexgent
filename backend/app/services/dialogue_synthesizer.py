import logging
from app.services.qwen_client import QwenClient
from app.services.oss_manager import OSSManager
from app.config import get_settings
from app.websocket.emitter import emit

logger = logging.getLogger(__name__)


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

        def _direction(line) -> str | None:
            """The acting notes for this line: the parenthetical the writer
            embedded ("(whispering, frantic)") plus any explicit direction
            field — stripped from the SPOKEN text, but handed to the instruct
            TTS so the delivery matches the writing."""
            import re
            bits = re.findall(r"\(([^)]+)\)", line.get("line") or "")
            if line.get("direction"):
                bits.append(str(line["direction"]))
            joined = ", ".join(b.strip() for b in bits if b.strip())
            return joined or None

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
                # not sink the whole batch: keep every line that succeeded,
                # skip the failure, and let the next export's missing-line
                # detection retry it.
                try:
                    audio = await self.qwen.synthesize_speech(
                        _spoken(line.get("line", "")), vid, voice.get("voice_model"),
                        instructions=_direction(line))
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        f"TTS failed for {name} (voice {vid}) s{scene['number']}l{li}: {e}")
                    emit("audio.tts.failed", {"scene_number": scene["number"], "line_index": li,
                                              "character": name, "error": str(e)[:200]}, pid)
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
