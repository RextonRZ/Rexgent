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


def _poster_crop_filter(focus_y: float) -> str:
    """A 16:10 crop window slid down a PORTRAIT frame: focus_y (0..100) is how
    far down the window sits. Landscape sources pass through untouched (the
    min() collapses to full height and y becomes 0), so one filter serves both
    orientations."""
    f = min(max(float(focus_y), 0.0), 100.0) / 100.0
    return f"crop=w=iw:h=min(ih\\,iw*10/16):x=0:y=(ih-oh)*{f:.4f}"


def extract_frame_at(clip_url: str, timestamp: float,
                     focus_y: float | None = None) -> bytes | None:
    """Return the frame at `timestamp` seconds as JPEG bytes (or None).
    ffmpeg reads http(s) URLs directly — no download step needed. This is the
    server-side poster capture: OSS serves clips without CORS headers, so a
    browser canvas capture would be tainted and unreadable. focus_y (0..100)
    crops a vertical clip to the card's 16:10 window at that height, so the
    poster IS the frame the user framed in the picker."""
    out = tempfile.mktemp(suffix=".jpg")
    cmd = [
        "ffmpeg", "-y", "-ss", str(max(0.0, timestamp)), "-i", clip_url,
        "-vframes", "1", "-q:v", "2",
    ]
    if focus_y is not None:
        cmd += ["-vf", _poster_crop_filter(focus_y)]
    cmd.append(out)
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


def extract_first_frame(clip_url: str) -> bytes | None:
    """Return the first frame of a clip as JPEG bytes (or None on failure).

    Mirrors extract_last_frame: same no-download (ffmpeg reads the URL
    directly), same temp-file handling, same best-effort try/except-and-return-None.
    Only the seek direction differs — `-ss 0` lands exactly on frame 0, so
    unlike -sseof there's no container-duration overshoot to guard against
    with -update; a plain -vframes 1 grab is enough. `-pix_fmt yuvj420p` is
    kept for the same reason as extract_last_frame: keeps the mjpeg encoder
    happy for any input pixel format."""
    out = tempfile.mktemp(suffix=".jpg")
    cmd = [
        "ffmpeg", "-y", "-ss", "0", "-i", clip_url,
        "-vframes", "1", "-pix_fmt", "yuvj420p", "-q:v", "2", out,
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
