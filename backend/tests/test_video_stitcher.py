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
