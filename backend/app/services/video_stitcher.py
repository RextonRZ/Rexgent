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
                path, tin, tout, mute, vol = clip, None, None, False, None
            else:
                path, tin, tout = clip.get("path"), clip.get("in"), clip.get("out")
                mute = bool(clip.get("mute"))
                # optional bed level for a KEPT dialogue soundtrack (the real
                # TTS voice overlays it, so it must sit underneath)
                vol = clip.get("volume")
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
            if not mute and vol is not None and float(vol) != 1.0:
                afade = f"volume={max(0.0, float(vol))},{afade}" if afade != "anull"                     else f"volume={max(0.0, float(vol))}"
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
                   ambient_volume=0.7, speech_gate=None, gate_level=0.06):
        """Final mix: TTS dialogue on top of a BED made of the video's own
        (model-generated) ambient audio + the user's BGM. Each dialogue segment
        is delayed to its timeline start; the whole bed ducks under speech
        (sidechaincompress) so voices stay intelligible. speech_gate dips the
        bed to gate_level over the given global (start, end) windows — the
        clips' own fake speech is silenced there while their music/ambience
        survives everywhere else. Returns output_path."""
        inputs = ["-i", video_path]
        filters, dlg_labels = [], []
        for i, seg in enumerate(dialogue_segments):
            inputs += ["-i", seg["audio_path"]]
            delay_ms = int(float(seg["start"]) * 1000)
            warp = seg.get("warp")
            if warp:
                # word-level repace: slice the line at its word boundaries and
                # atempo each slice onto the on-screen mouth's own rhythm
                # (pitch-preserving; placement pre-clamped every factor)
                k = len(warp)
                filters.append(f"[{i+1}:a]asplit={k}"
                               + "".join(f"[w{i}_{j}]" for j in range(k)))
                labels = []
                for j, piece in enumerate(warp):
                    tr = f"atrim=start={float(piece['start']):.3f}"
                    if piece.get("end") is not None:
                        tr += f":end={float(piece['end']):.3f}"
                    chain = [tr, "asetpts=PTS-STARTPTS"]
                    tp = float(piece.get("tempo") or 1.0)
                    if abs(tp - 1.0) >= 0.01:
                        chain.append(f"atempo={tp:.3f}")
                    filters.append(f"[w{i}_{j}]{','.join(chain)}[wp{i}_{j}]")
                    labels.append(f"[wp{i}_{j}]")
                filters.append(f"{''.join(labels)}concat=n={k}:v=0:a=1,"
                               f"adelay={delay_ms}|{delay_ms}[d{i}]")
            else:
                # pace the line to the on-screen mouth: atempo is
                # pitch-preserving, and placement pre-clamped the factor
                tempo = seg.get("tempo")
                chain = (f"atempo={float(tempo):.3f}," if tempo else "")
                filters.append(f"[{i+1}:a]{chain}adelay={delay_ms}|{delay_ms}[d{i}]")
            dlg_labels.append(f"[d{i}]")
        n = len(dialogue_segments)
        dlg = None
        if dlg_labels:
            # normalize=0 is LOAD-BEARING: amix's default scales every input by
            # 1/n, so 20 dialogue lines each played at 1/20th volume — inaudible.
            # Lines never overlap (placement guarantees it), so plain summing
            # cannot clip.
            filters.append(f"{''.join(dlg_labels)}amix=inputs={n}"
                           f":dropout_transition=0:normalize=0[dlg]")
            dlg = "[dlg]"
        # ── bed: the stitched video's own ambient track + optional BGM ──
        bed_labels = []
        if self._has_audio(video_path):
            amb_chain = [f"volume={ambient_volume}"]
            if speech_gate:
                windows = "+".join(f"between(t,{float(s):.3f},{float(e):.3f})"
                                   for s, e in speech_gate)
                amb_chain.append(f"volume={gate_level}:enable='{windows}'")
            filters.append(f"[0:a]{','.join(amb_chain)}[amb]")
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
            filters.append(f"{''.join(bed_labels)}amix=inputs=2"
                           f":dropout_transition=0:normalize=0[bed]")
            bed = "[bed]"
        elif bed_labels:
            bed = bed_labels[0]
        # ── combine (normalize=0 everywhere: never let amix shrink the voices) ──
        if bed and dlg:
            if duck:
                # duplicate the dialogue: one copy keys the compressor, one goes to the final mix
                filters.append("[dlg]asplit=2[dlgkey][dlgmix]")
                filters.append(f"{bed}[dlgkey]sidechaincompress=threshold=0.03:ratio=8[bedduck]")
                filters.append("[bedduck][dlgmix]amix=inputs=2"
                               ":dropout_transition=0:normalize=0[aout]")
            else:
                filters.append(f"{bed}{dlg}amix=inputs=2:dropout_transition=0:normalize=0[aout]")
            final_audio = "[aout]"
        else:
            final_audio = bed or dlg
        if final_audio is None:
            # nothing to mix — hand back the video untouched
            import shutil
            shutil.copyfile(video_path, output_path)
            return output_path
        # NO -shortest here: model clips' audio runs ~0.3s short of their video,
        # so a 9-chunk concat's audio ends seconds early and -shortest chopped
        # the picture with it (measured 22.0s out of a 25s cut). The padded
        # video is the master track; audio ending early is just silence.
        cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filters),
               "-map", "0:v", "-map", final_audio, "-c:v", "copy", "-c:a", "aac",
               "-movflags", "+faststart", output_path]
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
        # Matched to the editor preview's caption look (the approved design):
        # ~2.3% of frame height for the text, sitting 14% up from the bottom.
        # libass assumes a 384x288 script canvas, so these numbers are in
        # 288-height units: FontSize 7 = 45px on a 1920-tall phone frame.
        style = ("FontSize=7,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                 "Outline=1,Shadow=0,Bold=1,Alignment=2,MarginV=40")
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

    def pad_tail(self, video_path: str, output_path: str, seconds: float) -> str:
        """Hold the last frame (and silence) for `seconds` more — so a final
        voice line that outruns its shot finishes over a held picture instead
        of being cut off with the video."""
        vf = f"tpad=stop_mode=clone:stop_duration={seconds:.3f}"
        cmd = ["ffmpeg", "-y", "-i", video_path, "-vf", vf]
        if self._has_audio(video_path):
            cmd += ["-af", f"apad=pad_dur={seconds:.3f}"]
        cmd += ["-c:v", "libx264", "-crf", "20",
                "-movflags", "+faststart", output_path]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg tail pad failed: {proc.stderr[-800:]}")
        return output_path

    def fade_tail(self, video_path: str, output_path: str, fade: float = 0.8) -> str:
        """Fade picture and sound out together over the final `fade` seconds,
        so the episode lands on an ending instead of stopping mid-frame."""
        dur = self._duration(video_path)
        if dur <= 0:
            raise RuntimeError("cannot probe duration for the ending fade")
        fade = min(fade, dur / 2)
        st = max(0.0, dur - fade)
        cmd = ["ffmpeg", "-y", "-i", video_path,
               "-vf", f"fade=t=out:st={st:.3f}:d={fade:.3f}"]
        if self._has_audio(video_path):
            cmd += ["-af", f"afade=t=out:st={st:.3f}:d={fade:.3f}"]
        cmd += ["-c:v", "libx264", "-crf", "20",
                "-movflags", "+faststart", output_path]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg ending fade failed: {proc.stderr[-800:]}")
        return output_path
