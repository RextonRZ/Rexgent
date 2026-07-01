import subprocess
import tempfile
import os


class VideoStitcher:
    def stitch(self, clip_paths: list[str], output_path: str) -> str:
        """Concatenate clips into one MP4 via FFmpeg's concat demuxer.

        Re-encodes (instead of stream-copy) so clips that differ slightly still
        join cleanly, and drops audio to avoid stream-layout mismatches between
        clips. Captions ship separately as an .srt.
        """
        list_file = tempfile.mktemp(suffix=".txt")
        with open(list_file, "w", encoding="utf-8") as f:
            for path in clip_paths:
                safe = path.replace("'", "'\\''")
                f.write(f"file '{safe}'\n")
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
            "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-an", output_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        os.unlink(list_file)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg concat failed: {proc.stderr[-800:]}")
        return output_path

    def burn_subtitles(self, video_path: str, srt_path: str, output_path: str) -> str:
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"subtitles={srt_path}", "-c:a", "copy", output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path
