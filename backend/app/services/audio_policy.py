"""Keep the model's OWN soundtrack when it is clean.

A generated clip's audio is ONE mixed track: music + ambience + sound effects
+ (sometimes) hallucinated speech in a random language. Speaking shots used to
be muted wholesale to kill the fake speech — losing the score and the
door-slams with it. Instead, measure how much SPEECH the track actually
contains (local WebRTC VAD, no API cost): a clean track survives as a bed
under the real TTS voices; only genuinely speech-polluted tracks are muted.
"""
import logging
import subprocess

logger = logging.getLogger(__name__)

# ≤ this fraction of voiced 30ms frames still reads as ambience, not talking
SPEECH_KEEP_THRESHOLD = 0.10
# a kept dialogue-chunk bed plays UNDER the TTS voice, never against it
BED_VOLUME = 0.45

_SAMPLE_RATE = 16000
_FRAME_MS = 30
_FRAME_BYTES = int(_SAMPLE_RATE * _FRAME_MS / 1000) * 2  # s16le mono


def speech_ratio(video_path: str) -> float | None:
    """Fraction of 30ms frames the VAD marks as speech, or None when it cannot
    be measured (no VAD installed, no audio stream, ffmpeg missing) — callers
    treat None as unverifiable and fall back to the safe mute."""
    try:
        import webrtcvad
    except ImportError:
        logger.info("webrtcvad not installed — original-soundtrack keep disabled")
        return None
    try:
        proc = subprocess.run(
            ["ffmpeg", "-i", video_path, "-vn", "-ac", "1",
             "-ar", str(_SAMPLE_RATE), "-f", "s16le", "-acodec", "pcm_s16le",
             "pipe:1"],
            capture_output=True, timeout=120,
        )
        pcm = proc.stdout
        if proc.returncode != 0 or len(pcm) < _FRAME_BYTES * 10:  # <0.3s of audio
            return None
        vad = webrtcvad.Vad(2)  # 0..3, 2 = balanced aggressiveness
        voiced = total = 0
        for off in range(0, len(pcm) - _FRAME_BYTES + 1, _FRAME_BYTES):
            total += 1
            if vad.is_speech(pcm[off:off + _FRAME_BYTES], _SAMPLE_RATE):
                voiced += 1
        if total == 0:
            return None
        return voiced / total
    except Exception as e:  # noqa: BLE001 — measurement is best-effort
        logger.warning("speech_ratio failed for %s: %s", video_path, e)
        return None


def keep_clip_audio(has_dialogue: bool, ratio: float | None) -> bool:
    """Whether the clip's original soundtrack survives into the cut.
    Non-dialogue chunks always keep theirs (existing behavior). Dialogue
    chunks keep theirs only when measurably clean of fake speech."""
    if not has_dialogue:
        return True
    if ratio is None:
        return False  # can't verify -> the fake-speech risk wins
    return ratio <= SPEECH_KEEP_THRESHOLD
