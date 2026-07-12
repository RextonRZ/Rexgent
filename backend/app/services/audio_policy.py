"""Keep the model's OWN soundtrack when it is clean.

A generated clip's audio is ONE mixed track: music + ambience + sound effects
+ (sometimes) hallucinated speech in a random language. Speaking shots used to
be muted wholesale to kill the fake speech — losing the score and the
door-slams with it. Instead, measure how much SPEECH the track actually
contains (local WebRTC VAD, no API cost): a clean track survives as a bed
under the real TTS voices; only genuinely speech-polluted tracks are muted.
"""
import logging
import os
import re
import subprocess
import tempfile

logger = logging.getLogger(__name__)

# ≤ this fraction of voiced 30ms frames still reads as ambience, not talking
SPEECH_KEEP_THRESHOLD = 0.10
# a kept dialogue-chunk bed plays UNDER the TTS voice, never against it
BED_VOLUME = 0.45
# an ASR transcript with up to this many words is a stray vocalization in the
# score ("oh", "hey"), not a hallucinated dialogue line
MAX_BED_WORDS = 2

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


def first_spoken_onset(sentences: list) -> float | None:
    """First sentence that carries actual words -> its begin_time in seconds.
    Empty-text sentences are music the recognizer half-heard; their
    timestamps are noise. Pure function, testable."""
    span = spoken_span(sentences)
    return span[0] if span else None


def spoken_span(sentences: list) -> tuple[float, float] | None:
    """(onset, mouth_duration) of the clip's own speech: from the first
    worded sentence's begin to the last worded sentence's end. This is how
    long the on-screen mouth actually talks — the real TTS line stretches or
    compresses to match it. None when no words occur."""
    begins, ends = [], []
    for s in sentences or []:
        if not isinstance(s, dict):
            continue
        if str(s.get("text") or "").strip() and s.get("begin_time") is not None:
            begins.append(float(s["begin_time"]))
            end = s.get("end_time")
            ends.append(float(end) if end is not None else float(s["begin_time"]))
    if not begins:
        return None
    onset = round(min(begins) / 1000.0, 2)
    tail = round(max(ends) / 1000.0, 2)
    return onset, max(0.0, round(tail - onset, 2))


def speech_span(video_path: str) -> tuple[float, float] | None:
    """(onset, mouth_duration) of the clip's own (fake) speech — the model's
    audio tracks its on-screen mouth, so the real TTS line is placed at the
    onset AND paced across the mouth's span. Measured with fun-asr sentence
    timestamps: the VAD cannot do this job, its music bias flags frame one
    on every scored clip (measured 0.03-0.06s across a whole drama). None
    when no recognizable words occur."""
    wav = tempfile.mktemp(suffix=".wav")
    try:
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-vn", "-ac", "1",
             "-ar", str(_SAMPLE_RATE), wav],
            capture_output=True, timeout=120)
        if proc.returncode != 0 or not os.path.exists(wav):
            return None
        from app.config import get_settings
        settings = get_settings()
        if not settings.qwen_api_key:
            return None
        import dashscope
        from dashscope.audio.asr import Recognition
        dashscope.api_key = settings.qwen_api_key
        dashscope.base_websocket_api_url = (
            "wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference")
        rec = Recognition(model="fun-asr-realtime", format="wav",
                          sample_rate=_SAMPLE_RATE, callback=None)
        result = rec.call(wav)
        if getattr(result, "status_code", 200) != 200:
            raise RuntimeError(
                f"{getattr(result, 'status_code', '?')}: {getattr(result, 'message', '')}")
        sentences = result.get_sentence() or []
        if isinstance(sentences, dict):
            sentences = [sentences]
        return spoken_span(sentences)
    except Exception as e:  # noqa: BLE001 — measurement is best-effort
        logger.warning("speech_onset failed for %s: %s", video_path, e)
        return None
    finally:
        try:
            os.unlink(wav)
        except OSError:
            pass


def speech_onset(video_path: str) -> float | None:
    """Back-compat wrapper: just the onset from speech_span."""
    span = speech_span(video_path)
    return span[0] if span else None


def keep_clip_audio(has_dialogue: bool, ratio: float | None) -> bool:
    """Whether the clip's original soundtrack survives into the cut.
    Non-dialogue chunks always keep theirs (existing behavior). Dialogue
    chunks keep theirs only when measurably clean of fake speech."""
    if not has_dialogue:
        return True
    if ratio is None:
        return False  # can't verify -> the fake-speech risk wins
    return ratio <= SPEECH_KEEP_THRESHOLD


def transcribed_words(video_path: str) -> int:
    """How many real words Qwen ASR hears in the clip's soundtrack, or -1 when
    the measurement itself failed (callers treat -1 as unverifiable). The VAD
    upstream calls music 'speech' almost always (measured 0.98+ on real
    HappyHorse scores); a transcript separates an actual hallucinated dialogue
    line from a score with no words in it."""
    wav = tempfile.mktemp(suffix=".wav")
    try:
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-vn", "-ac", "1",
             "-ar", str(_SAMPLE_RATE), wav],
            capture_output=True, timeout=120)
        if proc.returncode != 0 or not os.path.exists(wav):
            return -1
        from app.config import get_settings
        settings = get_settings()
        if not settings.qwen_api_key:
            return -1
        import dashscope
        dashscope.base_http_api_url = settings.qwen_video_base_url
        resp = dashscope.MultiModalConversation.call(
            model="qwen3-asr-flash",
            api_key=settings.qwen_api_key,
            messages=[{"role": "user",
                       "content": [{"audio": "file://" + wav.replace("\\", "/")}]}],
            result_format="message")
        if getattr(resp, "status_code", 200) != 200:
            raise RuntimeError(
                f"{getattr(resp, 'status_code', '?')}: {getattr(resp, 'message', '')}")
        content = resp.output.choices[0].message.content
        text = " ".join(
            part.get("text", "") for part in (content if isinstance(content, list) else [])
            if isinstance(part, dict))
        words = [w for w in re.split(r"\s+", text.strip())
                 if any(ch.isalnum() for ch in w)]
        return len(words)
    except Exception as e:  # noqa: BLE001 — measurement is best-effort
        logger.warning("ASR word check failed for %s: %s", video_path, e)
        return -1
    finally:
        try:
            os.unlink(wav)
        except OSError:
            pass


def bed_decision(video_path: str, has_dialogue: bool) -> tuple[bool, float | None]:
    """(mute, volume) for one cut chunk. Non-dialogue chunks keep their full
    original audio. Dialogue chunks keep a quiet bed under the TTS voice when
    the track carries no real words: the free VAD answers first, and when it
    cries speech (its music bias) the ASR transcript gets the final say."""
    if not has_dialogue:
        return False, None
    ratio = speech_ratio(video_path)
    if keep_clip_audio(True, ratio):
        return False, BED_VOLUME
    words = transcribed_words(video_path)
    if 0 <= words <= MAX_BED_WORDS:
        logger.info("bed kept: ASR heard %d word(s) despite VAD ratio %.2f",
                    words, ratio or -1.0)
        return False, BED_VOLUME
    return True, None
