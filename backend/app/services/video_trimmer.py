import subprocess
import tempfile


class VideoTrimmer:
    def trim_from_url(self, video_url: str, start_seconds: float, end_seconds: float) -> str:
        """Trim a clip to [start, end]. Returns the local output path."""
        output = tempfile.mktemp(suffix=".mp4")
        duration = max(0.0, end_seconds - start_seconds)
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_seconds),
            "-i", video_url,
            "-t", str(duration),
            "-c", "copy",
            output,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return output
