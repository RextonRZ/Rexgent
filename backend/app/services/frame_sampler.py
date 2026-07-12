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


def extract_frame_at(clip_url: str, timestamp: float) -> bytes | None:
    """Return the frame at `timestamp` seconds as JPEG bytes (or None).
    ffmpeg reads http(s) URLs directly — no download step needed. This is the
    server-side poster capture: OSS serves clips without CORS headers, so a
    browser canvas capture would be tainted and unreadable."""
    out = tempfile.mktemp(suffix=".jpg")
    cmd = [
        "ffmpeg", "-y", "-ss", str(max(0.0, timestamp)), "-i", clip_url,
        "-vframes", "1", "-q:v", "2", out,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
        if os.path.exists(out):
            with open(out, "rb") as f:
                data = f.read()
            os.unlink(out)
            return data
    except Exception:
        pass
    return None


def extract_last_frame(clip_url: str) -> bytes | None:
    """Return the final frame of a clip as JPEG bytes (or None on failure).

    Model-generated mp4s report a container duration slightly PAST their last
    packet, so seeking `-sseof -0.1` lands beyond the final frame and ffmpeg
    writes nothing (verified against real Wan/HappyHorse clips). Decode the
    last second instead and let `-update 1` keep overwriting until the true
    final frame; `-pix_fmt yuvj420p` keeps the mjpeg encoder happy for any
    input pixel format."""
    out = tempfile.mktemp(suffix=".jpg")
    cmd = [
        "ffmpeg", "-y", "-sseof", "-1", "-i", clip_url,
        "-update", "1", "-pix_fmt", "yuvj420p", "-q:v", "2", out,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
        if os.path.exists(out) and os.path.getsize(out) > 0:
            with open(out, "rb") as f:
                data = f.read()
            os.unlink(out)
            return data
    except Exception:
        pass
    return None
