from unittest.mock import patch
from app.services.video_stitcher import VideoStitcher


def test_normalise_canvas_follows_delivery_format():
    # vertical by default; landscape when the drama was created 16:9
    assert "scale=1080:1920" in VideoStitcher._vf_for("9:16")
    assert "pad=1080:1920" in VideoStitcher._vf_for("9:16")
    assert "scale=1920:1080" in VideoStitcher._vf_for("16:9")
    # unknown ratios fall back to the vertical default
    assert "scale=1080:1920" in VideoStitcher._vf_for("weird")


def test_burn_subtitles_styles_and_reencodes():
    st = VideoStitcher()
    with patch("subprocess.run") as run:
        run.return_value.returncode = 0
        st.burn_subtitles("/tmp/v.mp4", "/tmp/captions.srt", "/tmp/out.mp4")
        args = run.call_args[0][0]
    joined = " ".join(args)
    assert "subtitles=captions.srt" in joined   # relative name, cwd-based
    assert "force_style" in joined
    assert "libx264" in joined                   # burning requires re-encode


def test_mix_tracks_builds_duck_filter():
    st = VideoStitcher()
    with patch("subprocess.run") as run:
        run.return_value.returncode = 0
        st.mix_tracks(
            video_path="v.mp4",
            dialogue_segments=[{"audio_path": "a.wav", "start": 10.0}],
            bgm_path="bgm.mp3", output_path="out.mp4", bgm_volume=0.3, duck=True)
        args = run.call_args[0][0]
    joined = " ".join(args)
    assert "adelay" in joined            # dialogue placed at offset
    assert "sidechaincompress" in joined  # ducking present
    assert "amix" in joined


def test_mix_never_lets_amix_shrink_the_voices():
    # amix's default normalization scales each input by 1/n — with 20 dialogue
    # lines every voice played at 1/20th volume (sounded like NO audio).
    # normalize=0 on every amix keeps voices at full level.
    st = VideoStitcher()
    with patch("subprocess.run") as run, \
         patch.object(VideoStitcher, "_has_audio", return_value=True):
        run.return_value.returncode = 0
        st.mix_tracks("v.mp4",
                      [{"audio_path": f"l{i}.wav", "start": float(i * 3)} for i in range(20)],
                      "bgm.mp3", "out.mp4", bgm_volume=0.3, duck=True)
        joined = " ".join(run.call_args[0][0])
    for part in joined.split(";"):
        if "amix" in part:
            assert "normalize=0" in part, f"amix without normalize=0: {part}"


def test_mix_tracks_constant_low_when_duck_false():
    st = VideoStitcher()
    with patch("subprocess.run") as run:
        run.return_value.returncode = 0
        st.mix_tracks("v.mp4", [{"audio_path": "a.wav", "start": 0.0}], "bgm.mp3", "out.mp4", 0.3, duck=False)
        joined = " ".join(run.call_args[0][0])
    assert "sidechaincompress" not in joined
    assert "amix" in joined


def test_mix_tracks_applies_user_volume_and_fade():
    st = VideoStitcher()
    with patch("subprocess.run") as run, patch.object(VideoStitcher, "_duration", return_value=30.0):
        run.return_value.returncode = 0
        st.mix_tracks(
            "v.mp4", [], "bgm.mp3", "out.mp4",
            bgm_volume=0.6, duck=True, bgm_fade_in=2.0, bgm_fade_out=3.0)
        joined = " ".join(run.call_args[0][0])
    assert "volume=0.6" in joined         # the volume the user set
    assert "afade=t=in:st=0:d=2.0" in joined
    assert "afade=t=out" in joined        # fade-out anchored near the end


def test_mix_tracks_music_only_needs_no_dialogue():
    # music with no dialogue must still reach the output (BGM-only export)
    st = VideoStitcher()
    with patch("subprocess.run") as run:
        run.return_value.returncode = 0
        st.mix_tracks("v.mp4", [], "bgm.mp3", "out.mp4", bgm_volume=1.0, duck=True)
        args = run.call_args[0][0]
    joined = " ".join(args)
    assert "[bgm]" in joined
    assert args[-1] == "out.mp4"


def test_stitch_keeps_original_audio_with_chunk_fades():
    # the model's own audio rides along as the ambient bed, faded at both ends
    # of every chunk so clip-to-clip cuts don't click
    st = VideoStitcher()
    with patch("subprocess.run") as run, \
         patch.object(VideoStitcher, "_has_audio", return_value=True), \
         patch.object(VideoStitcher, "_duration", return_value=5.0):
        run.return_value.returncode = 0
        st.stitch(["/tmp/a.mp4"], "/tmp/out.mp4")
        normalise = " ".join(run.call_args_list[0][0][0])
    assert "afade=t=in:st=0:d=0.25" in normalise
    assert "afade=t=out:st=4.750:d=0.25" in normalise
    assert "-an" not in normalise.split()   # audio no longer dropped
    assert "aac" in normalise


def test_stitch_fills_silence_when_clip_has_no_audio():
    # a silent clip still gets a uniform aac stream so the concat holds
    st = VideoStitcher()
    with patch("subprocess.run") as run, \
         patch.object(VideoStitcher, "_has_audio", return_value=False), \
         patch.object(VideoStitcher, "_duration", return_value=5.0):
        run.return_value.returncode = 0
        st.stitch(["/tmp/a.mp4"], "/tmp/out.mp4")
        normalise = " ".join(run.call_args_list[0][0][0])
    assert "anullsrc" in normalise
    assert "-shortest" in normalise


def test_mix_uses_video_ambient_as_bed_and_ducks_it():
    # the stitched video's own audio joins the bed with BGM; the whole bed
    # ducks under dialogue so voices stay clear
    st = VideoStitcher()
    with patch("subprocess.run") as run, \
         patch.object(VideoStitcher, "_has_audio", return_value=True):
        run.return_value.returncode = 0
        st.mix_tracks("v.mp4", [{"audio_path": "a.wav", "start": 0.0}],
                      "bgm.mp3", "out.mp4", bgm_volume=0.3, duck=True,
                      ambient_volume=0.7)
        joined = " ".join(run.call_args[0][0])
    assert "[0:a]volume=0.7[amb]" in joined            # ambient bed present
    assert "[amb][bgm]amix" in joined                  # bed = ambient + music
    assert "[bed][dlgkey]sidechaincompress" in joined  # bed ducks under speech


def test_stitch_mutes_dialogue_shot_audio():
    # a dialogue shot's model audio fakes its own speech — it must be silenced
    # so only the real TTS voices speak; the stream stays for the concat
    st = VideoStitcher()
    with patch("subprocess.run") as run, \
         patch.object(VideoStitcher, "_has_audio", return_value=True), \
         patch.object(VideoStitcher, "_duration", return_value=5.0):
        run.return_value.returncode = 0
        st.stitch([{"path": "/tmp/a.mp4", "in": None, "out": None, "mute": True}],
                  "/tmp/out.mp4")
        normalise = " ".join(run.call_args_list[0][0][0])
    assert "volume=0" in normalise
    assert "afade" not in normalise  # nothing to fade — it's silent


def test_mix_ambient_only_still_produces_audio():
    # no dialogue, no BGM — the ambient bed alone must reach the output
    st = VideoStitcher()
    with patch("subprocess.run") as run, \
         patch.object(VideoStitcher, "_has_audio", return_value=True):
        run.return_value.returncode = 0
        st.mix_tracks("v.mp4", [], None, "out.mp4")
        args = run.call_args[0][0]
    assert "[amb]" in " ".join(args)
    assert args[args.index("-map") + 1] == "0:v"


def test_mix_tracks_builds_word_warp_chain():
    st = VideoStitcher()
    with patch("subprocess.run") as run:
        run.return_value.returncode = 0
        st.mix_tracks("v.mp4",
                      [{"audio_path": "a.wav", "start": 3.0,
                        "warp": [{"start": 0.0, "end": 0.6, "tempo": 1.0},
                                 {"start": 0.6, "end": 1.1, "tempo": 0.6},
                                 {"start": 1.1, "end": None, "tempo": 1.0}]}],
                      "bgm.mp3", "out.mp4", bgm_volume=0.3, duck=True)
        joined = " ".join(run.call_args[0][0])
    assert "asplit=3" in joined
    assert "atrim=start=0.600:end=1.100" in joined
    assert "atempo=0.600" in joined
    assert "concat=n=3:v=0:a=1" in joined
    assert "adelay=3000|3000" in joined


def test_mix_tracks_gates_native_speech_windows():
    st = VideoStitcher()
    with patch("subprocess.run") as run, \
         patch.object(VideoStitcher, "_has_audio", return_value=True):
        run.return_value.returncode = 0
        st.mix_tracks("v.mp4", [{"audio_path": "a.wav", "start": 1.0}],
                      None, "out.mp4",
                      speech_gate=[(0.85, 4.15), (10.35, 12.65)])
        joined = " ".join(run.call_args[0][0])
    # the bed dips to near-silence exactly over the fake speech, and ONLY there
    assert "between(t,0.850,4.150)" in joined
    assert "between(t,10.350,12.650)" in joined
    assert "volume=0.06" in joined


def test_tail_hold_clones_last_frame_and_pads_silence():
    # scene breathing: a boundary chunk holds its final frame for `tail_hold`
    # seconds with padded silence. The trim must move to the INPUT side —
    # an output -t would chop the freeze right back off.
    st = VideoStitcher()
    with patch("subprocess.run") as run, \
         patch.object(VideoStitcher, "_duration", return_value=6.0), \
         patch.object(VideoStitcher, "_has_audio", return_value=True):
        run.return_value.returncode = 0
        st.stitch([{"path": "a.mp4", "in": 0.5, "out": 4.5, "mute": False,
                    "tail_hold": 0.5},
                   {"path": "b.mp4", "in": None, "out": 4.0, "mute": False}],
                  "out.mp4", "9:16")
        cmd_a = " ".join(run.call_args_list[0][0][0])
        cmd_b = " ".join(run.call_args_list[1][0][0])
    assert "tpad=stop_mode=clone:stop_duration=0.500" in cmd_a
    assert "apad=pad_dur=0.500" in cmd_a
    # trim on the INPUT side: -t precedes -i for the held chunk
    assert cmd_a.index(" -t 4.000") < cmd_a.index(" -i a.mp4")
    # a chunk without a hold keeps the original output-side construction
    assert "tpad" not in cmd_b and "apad" not in cmd_b
    assert cmd_b.index(" -i b.mp4") < cmd_b.index(" -t 4.000")
