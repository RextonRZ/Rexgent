import subprocess
import tempfile
import os


class VideoStitcher:
    # Canvas per delivery format; clips of any source resolution letterbox
    # onto it instead of breaking the concat.
    _CANVAS = {"9:16": (1080, 1920), "16:9": (1920, 1080)}
    # per-chunk audio fade so clip-to-clip cuts don't click/jar
    _AUDIO_FADE = 0.25

    @classmethod
    def _vf_for(cls, ratio: str) -> str:
        w, h = cls._CANVAS.get(ratio, cls._CANVAS["9:16"])
        return (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,fps=24,format=yuv420p")

    @staticmethod
    def _has_audio(path: str) -> bool:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
            capture_output=True, text=True,
        )
        return "audio" in (proc.stdout or "")

    def stitch(self, clips: list, output_path: str, ratio: str = "9:16") -> str:
        """Concatenate clips into one MP4.

        `clips` is a list of paths (str) or dicts
        {"path": str, "in": float|None, "out": float|None, "mute": bool} for
        per-clip trim / audio policy. Each clip is first normalised to the
        drama's delivery canvas (vertical 1080x1920 by default) at 24fps (and
        trimmed), so mixed-resolution / imported media join cleanly; the
        normalised parts are then concatenated with a stream copy.

        The model's ORIGINAL audio is kept as the ambient bed, with a short
        fade in/out on every chunk so transitions don't cut audibly. Clips
        with no audio stream get silence so the concat's streams stay uniform.
        mute=True silences a chunk's source audio entirely — used for dialogue
        shots, whose model-generated fake speech would otherwise murmur under
        the real TTS voices.
        """
        norm_dir = tempfile.mkdtemp()
        norm_paths = []
        for i, clip in enumerate(clips):
            if isinstance(clip, str):
                path, tin, tout, mute = clip, None, None, False
            else:
                path, tin, tout = clip.get("path"), clip.get("in"), clip.get("out")
                mute = bool(clip.get("mute"))
            norm = os.path.join(norm_dir, f"n{i:03d}.mp4")
            # effective chunk length places the fade-out; fall back to probe
            if tout is not None:
                eff = float(tout) - float(tin or 0.0)
            else:
                eff = max(0.0, self._duration(path) - float(tin or 0.0))
            f = self._AUDIO_FADE
            has_audio = self._has_audio(path)
            cmd = ["ffmpeg", "-y"]
            if tin:
                cmd += ["-ss", f"{float(tin):.3f}"]
            cmd += ["-i", path]
            if not has_audio:
                # silent source: manufacture a silence track so every chunk has
                # a uniform aac stream for the copy-concat
                cmd += ["-f", "lavfi",
                        "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
            if tout is not None and eff > 0:
                cmd += ["-t", f"{eff:.3f}"]
            if mute:
                # dialogue shot: kill the model's fake speech; TTS carries the voice
                afade = "volume=0"
            elif eff > 2 * f:
                afade = f"afade=t=in:st=0:d={f},afade=t=out:st={max(0.0, eff - f):.3f}:d={f}"
            else:
                afade = "anull"
            cmd += ["-vf", self._vf_for(ratio), "-af", afade]
            if not has_audio:
                cmd += ["-map", "0:v", "-map", "1:a", "-shortest"]
            cmd += [
                "-c:v", "libx264", "-crf", "20",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", norm,
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
                   bgm_volume=0.3, duck=True, bgm_fade_in=0.0, bgm_fade_out=0.0,
                   ambient_volume=0.7):
        """Final mix: TTS dialogue on top of a BED made of the video's own
        (model-generated) ambient audio + the user's BGM. Each dialogue segment
        is delayed to its timeline start; the whole bed ducks under speech
        (sidechaincompress) so voices stay intelligible. Returns output_path."""
        inputs = ["-i", video_path]
        filters, dlg_labels = [], []
        for i, seg in enumerate(dialogue_segments):
            inputs += ["-i", seg["audio_path"]]
            delay_ms = int(float(seg["start"]) * 1000)
            filters.append(f"[{i+1}:a]adelay={delay_ms}|{delay_ms}[d{i}]")
            dlg_labels.append(f"[d{i}]")
        n = len(dialogue_segments)
        dlg = None
        if dlg_labels:
            filters.append(f"{''.join(dlg_labels)}amix=inputs={n}:dropout_transition=0[dlg]")
            dlg = "[dlg]"
        # ── bed: the stitched video's own ambient track + optional BGM ──
        bed_labels = []
        if self._has_audio(video_path):
            filters.append(f"[0:a]volume={ambient_volume}[amb]")
            bed_labels.append("[amb]")
        if bgm_path:
            bgm_idx = n + 1
            inputs += ["-i", bgm_path]
            # volume + the user's fades, in order, on the music
            bgm_chain = [f"volume={bgm_volume}"]
            if bgm_fade_in and bgm_fade_in > 0:
                bgm_chain.append(f"afade=t=in:st=0:d={bgm_fade_in}")
            if bgm_fade_out and bgm_fade_out > 0:
                vdur = self._duration(video_path)
                if vdur > 0:
                    start = max(0.0, vdur - bgm_fade_out)
                    bgm_chain.append(f"afade=t=out:st={start:.2f}:d={bgm_fade_out}")
            filters.append(f"[{bgm_idx}:a]{','.join(bgm_chain)}[bgm]")
            bed_labels.append("[bgm]")
        bed = None
        if len(bed_labels) == 2:
            filters.append(f"{''.join(bed_labels)}amix=inputs=2:dropout_transition=0[bed]")
            bed = "[bed]"
        elif bed_labels:
            bed = bed_labels[0]
        # ── combine ──
        if bed and dlg:
            if duck:
                # duplicate the dialogue: one copy keys the compressor, one goes to the final mix
                filters.append("[dlg]asplit=2[dlgkey][dlgmix]")
                filters.append(f"{bed}[dlgkey]sidechaincompress=threshold=0.03:ratio=8[bedduck]")
                filters.append("[bedduck][dlgmix]amix=inputs=2:dropout_transition=0[aout]")
            else:
                filters.append(f"{bed}{dlg}amix=inputs=2:dropout_transition=0[aout]")
            final_audio = "[aout]"
        else:
            final_audio = bed or dlg
        if final_audio is None:
            # nothing to mix — hand back the video untouched
            import shutil
            shutil.copyfile(video_path, output_path)
            return output_path
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
