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
        """Build an .srt from sequential clips. Each clip: {dialogue, duration}."""
        lines: list[str] = []
        index = 1
        current = 0.0

        for clip in clips_with_dialogue:
            dialogue = clip.get("dialogue")
            duration = clip.get("duration", 5)
            if dialogue:
                start = self._format_time(current)
                end = self._format_time(current + duration)
                lines.append(str(index))
                lines.append(f"{start} --> {end}")
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
