import subprocess
import tempfile
import os


class VideoStitcher:
    # Canvas per delivery format; clips of any source resolution letterbox
    # onto it instead of breaking the concat.
    _CANVAS = {"9:16": (1080, 1920), "16:9": (1920, 1080)}

    @classmethod
    def _vf_for(cls, ratio: str) -> str:
        w, h = cls._CANVAS.get(ratio, cls._CANVAS["9:16"])
        return (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,fps=24,format=yuv420p")

    def stitch(self, clips: list, output_path: str, ratio: str = "9:16") -> str:
        """Concatenate clips into one MP4.

        `clips` is a list of paths (str) or dicts
        {"path": str, "in": float|None, "out": float|None} for per-clip trim.
        Each clip is first normalised to the drama's delivery canvas
        (vertical 1080x1920 by default) at 24fps (and trimmed), so
        mixed-resolution / imported media join cleanly; the normalised parts
        are then concatenated with a stream copy. Audio is dropped (captions
        are burned + shipped as an .srt; dialogue and music are mixed later).
        """
        norm_dir = tempfile.mkdtemp()
        norm_paths = []
        for i, clip in enumerate(clips):
            if isinstance(clip, str):
                path, tin, tout = clip, None, None
            else:
                path, tin, tout = clip.get("path"), clip.get("in"), clip.get("out")
            norm = os.path.join(norm_dir, f"n{i:03d}.mp4")
            cmd = ["ffmpeg", "-y"]
            if tin:
                cmd += ["-ss", f"{float(tin):.3f}"]
            cmd += ["-i", path]
            if tout is not None:
                dur = float(tout) - float(tin or 0.0)
                if dur > 0:
                    cmd += ["-t", f"{dur:.3f}"]
            cmd += [
                "-vf", self._vf_for(ratio),
                "-c:v", "libx264", "-crf", "20", "-an", norm,
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise RuntimeError(f"ffmpeg normalise failed: {proc.stderr[-800:]}")
            norm_paths.append(norm)

        list_file = tempfile.mktemp(suffix=".txt")
        with open(list_file, "w", encoding="utf-8") as f:
            for p in norm_paths:
                safe = p.replace("'", "'\\''")
                f.write(f"file '{safe}'\n")
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
            "-c", "copy", "-movflags", "+faststart", output_path,
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

    def mix_tracks(self, video_path, dialogue_segments, bgm_path, output_path,
                   bgm_volume=0.3, duck=True):
        """Build one dialogue track (each segment delayed to its start, then amix),
        optionally duck a BGM bed beneath it (sidechaincompress), and mux onto the
        silent video. Returns output_path."""
        inputs = ["-i", video_path]
        filters, dlg_labels = [], []
        for i, seg in enumerate(dialogue_segments):
            inputs += ["-i", seg["audio_path"]]
            delay_ms = int(float(seg["start"]) * 1000)
            filters.append(f"[{i+1}:a]adelay={delay_ms}|{delay_ms}[d{i}]")
            dlg_labels.append(f"[d{i}]")
        n = len(dialogue_segments)
        final_audio = None
        if dlg_labels:
            filters.append(f"{''.join(dlg_labels)}amix=inputs={n}:dropout_transition=0[dlg]")
            final_audio = "[dlg]"
        if bgm_path:
            bgm_idx = n + 1
            inputs += ["-i", bgm_path]
            filters.append(f"[{bgm_idx}:a]volume={bgm_volume}[bgm]")
            if duck and final_audio:
                # duplicate the dialogue: one copy keys the compressor, one goes to the final mix
                filters.append("[dlg]asplit=2[dlgkey][dlgmix]")
                filters.append("[bgm][dlgkey]sidechaincompress=threshold=0.03:ratio=8[bgmduck]")
                filters.append("[bgmduck][dlgmix]amix=inputs=2:dropout_transition=0[aout]")
                final_audio = "[aout]"
            elif final_audio:
                filters.append("[bgm][dlg]amix=inputs=2:dropout_transition=0[aout]")
                final_audio = "[aout]"
            else:
                final_audio = "[bgm]"
        cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filters),
               "-map", "0:v", "-map", final_audio, "-c:v", "copy", "-c:a", "aac",
               "-shortest", "-movflags", "+faststart", output_path]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg mix failed: {proc.stderr[-800:]}")
        return output_path

    def burn_subtitles(self, video_path: str, srt_path: str, output_path: str) -> str:
        """Burn captions into the picture — non-negotiable for the vertical
        format (short dramas are watched muted-first). Styled for a phone
        screen: bold, outlined, bottom-centred, raised clear of player UI.
        Runs with cwd at the .srt so the filter arg needs no path escaping
        (Windows drive colons break ffmpeg filter parsing)."""
        style = ("FontSize=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                 "Outline=2,Shadow=0,Bold=1,Alignment=2,MarginV=120")
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"subtitles={os.path.basename(srt_path)}:force_style='{style}'",
            "-c:v", "libx264", "-crf", "20", "-c:a", "copy",
            "-movflags", "+faststart", output_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              cwd=os.path.dirname(srt_path) or ".")
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg subtitle burn failed: {proc.stderr[-800:]}")
        return output_path
