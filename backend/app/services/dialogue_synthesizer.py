from app.services.qwen_client import QwenClient
from app.services.oss_manager import OSSManager
from app.config import get_settings
from app.websocket.emitter import emit


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
    def __init__(self):
        s = get_settings()
        self.qwen = QwenClient(s)
        self.oss = OSSManager(s)

    async def synthesize_lines(self, project_id, scenes, voice_by_name) -> list[dict]:
        pid = str(project_id)
        total = sum(len(s.get("dialogue_json") or []) for s in scenes)
        idx, rows = 0, []
        for scene in scenes:
            for li, line in enumerate(scene.get("dialogue_json") or []):
                idx += 1
                name = line.get("character")
                voice = voice_by_name.get(name) or {}
                vid = voice.get("voice_id") or "designed:narrator"
                emit("audio.tts.started", {"scene_number": scene["number"], "line_index": li,
                                           "index": idx, "total": total}, pid)
                audio = await self.qwen.synthesize_speech(line.get("line", ""), vid, voice.get("voice_model"))
                key = self.oss.get_project_path(pid, "audio", f"s{scene['number']}_l{li}.wav")
                url = self.oss.upload_bytes(audio, key, content_type="audio/wav")
                rows.append({"project_id": project_id, "scene_number": scene["number"], "line_index": li,
                             "character_name": name, "text": line.get("line", ""), "voice_id": vid,
                             "audio_url": url, "duration_seconds": probe_duration(audio)})
                emit("audio.tts.completed", {"scene_number": scene["number"], "line_index": li,
                                             "index": idx, "total": total}, pid)
        return rows
