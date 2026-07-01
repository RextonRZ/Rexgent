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

    @staticmethod
    def _duration(path: str) -> float:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True,
        )
        try:
            return float(proc.stdout.strip())
        except (ValueError, TypeError):
            return 0.0

    def add_audio(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        volume: float = 1.0,
        fade_in: float = 0.0,
        fade_out: float = 0.0,
    ) -> str:
        """Mix a music track over the (silent) video: volume + fades, trimmed to
        the video length. Video stream is copied; only audio is encoded."""
        filters = [f"volume={max(0.0, volume)}"]
        if fade_in > 0:
            filters.append(f"afade=t=in:st=0:d={fade_in}")
        if fade_out > 0:
            dur = self._duration(video_path)
            if dur > 0:
                start = max(0.0, dur - fade_out)
                filters.append(f"afade=t=out:st={start:.2f}:d={fade_out}")
        afilter = ",".join(filters)
        cmd = [
            "ffmpeg", "-y", "-i", video_path, "-i", audio_path,
            "-filter_complex", f"[1:a]{afilter}[a]",
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-shortest",
            "-movflags", "+faststart", output_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg audio mux failed: {proc.stderr[-800:]}")
        return output_path

    def burn_subtitles(self, video_path: str, srt_path: str, output_path: str) -> str:
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"subtitles={srt_path}", "-c:a", "copy", output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path
