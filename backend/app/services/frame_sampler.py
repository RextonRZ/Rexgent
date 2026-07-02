import subprocess
import tempfile
import os


def even_timestamps(duration: float, count: int = 3) -> list[float]:
    if duration <= 0 or count <= 0:
        return []
    return [round(duration / (count + 1) * (i + 1), 3) for i in range(count)]


def sample_frames(clip_path_or_url: str, duration: float, count: int = 3) -> list[bytes]:
    """Extract `count` JPEG frames evenly spaced. Returns raw bytes per frame."""
    frames: list[bytes] = []
    for ts in even_timestamps(duration, count):
        out = tempfile.mktemp(suffix=".jpg")
        cmd = [
            "ffmpeg", "-y", "-ss", str(ts), "-i", clip_path_or_url,
            "-vframes", "1", "-q:v", "2", out,
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=20)
            if os.path.exists(out):
                with open(out, "rb") as f:
                    frames.append(f.read())
                os.unlink(out)
        except Exception:
            pass
    return frames


def extract_last_frame(clip_url: str) -> bytes | None:
    """Return the final frame of a clip as JPEG bytes (or None on failure)."""
    out = tempfile.mktemp(suffix=".jpg")
    cmd = [
        "ffmpeg", "-y", "-sseof", "-0.1", "-i", clip_url,
        "-vframes", "1", "-q:v", "2", out,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=20)
        if os.path.exists(out):
            with open(out, "rb") as f:
                data = f.read()
            os.unlink(out)
            return data
    except Exception:
        pass
    return None
