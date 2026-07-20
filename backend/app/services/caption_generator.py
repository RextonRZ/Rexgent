import re

_WORDS_PER_SEC = 2.6    # natural delivery pace — matches the boarding fitter
_CJK_CHARS_PER_SEC = 4.5  # spoken pace of Chinese/Japanese/Korean, per character
_SPEECH_ONSET = 0.35    # native talk takes a breath before the first word
_CAPTION_HOLD = 1.0     # the caption lingers this long after the line ends

_CJK_RE = re.compile(r"[一-鿿぀-ヿ가-힣]")


def _spoken_seconds(text: str) -> float:
    """How long the line takes to say. CJK has NO spaces, so a naive
    word-split counted a whole Chinese sentence as ONE word (~0.4s) and the
    caption vanished instantly — count CJK by CHARACTER, Latin by word."""
    t = str(text or "")
    cjk = len(_CJK_RE.findall(t))
    latin = len([w for w in re.split(r"\s+", t)
                 if w and not all(_CJK_RE.match(c) for c in w)])
    return cjk / _CJK_CHARS_PER_SEC + latin / _WORDS_PER_SEC


class CaptionGenerator:
    def generate_srt_from_segments(self, segments: list[dict]) -> str:
        """Build an .srt from placed dialogue segments — the same offsets the
        audio mix uses ({start, duration, text}), so burned captions appear
        exactly when the line is spoken instead of drifting with shot lengths."""
        lines: list[str] = []
        index = 1
        ordered = sorted((s for s in segments if s.get("text")),
                         key=lambda s: float(s.get("start") or 0.0))
        for i, seg in enumerate(ordered):
            start = float(seg.get("start") or 0.0)
            end = start + max(float(seg.get("duration") or 0.0), 1.0)
            nxt = ordered[i + 1] if i + 1 < len(ordered) else None
            if nxt is not None:
                end = min(end, max(start + 0.5, float(nxt.get("start") or 0.0) - 0.05))
            lines.append(str(index))
            lines.append(f"{self._format_time(start)} --> {self._format_time(end)}")
            lines.append(str(seg["text"]))
            lines.append("")
            index += 1
        return "\n".join(lines)

    def generate_srt(self, clips_with_dialogue: list[dict]) -> str:
        """Build an .srt from sequential clips ({dialogue, duration}). The
        caption follows the SPOKEN line, not the clip: it appears at the
        estimated speech onset and stays _CAPTION_HOLD seconds after the line
        ends, clamped to the clip — a 2-word line inside a 5s clip no longer
        wears its caption for the whole clip."""
        lines: list[str] = []
        index = 1
        current = 0.0

        for clip in clips_with_dialogue:
            dialogue = clip.get("dialogue")
            duration = float(clip.get("duration", 5) or 5)
            if dialogue:
                spoken = _spoken_seconds(dialogue)
                start_s = current + min(_SPEECH_ONSET, duration)
                end_s = min(current + duration, start_s + spoken + _CAPTION_HOLD)
                lines.append(str(index))
                lines.append(f"{self._format_time(start_s)} --> {self._format_time(end_s)}")
                lines.append(dialogue)
                lines.append("")
                index += 1
            current += duration

        return "\n".join(lines)

    def _format_time(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int(round((seconds - int(seconds)) * 1000))
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
