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
