"""Shared language-control helper.

Threaded through script generation, structuring, plot-gap detection, and
character extraction so the whole pipeline can run in Chinese (Fix #9).
"""

_INSTRUCTIONS = {
    "zh": (
        "\n\nIMPORTANT: Respond entirely in Simplified Chinese (中文). "
        "All generated prose, descriptions, and field values must be in Chinese."
    ),
}


def language_instruction(language: str) -> str:
    return _INSTRUCTIONS.get(language, "")
