class CaptionGenerator:
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
