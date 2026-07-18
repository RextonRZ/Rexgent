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


import re as _re

_CJK_RE = _re.compile(r"[一-鿿]")


def detect_language(text) -> str:
    """"zh" when the text carries Chinese prose, else "en". Reads the SCRIPT
    rather than trusting a threaded parameter: extraction and other
    script-consuming stages then match the script's real language even when
    the run request forgot to say so."""
    return "zh" if len(_CJK_RE.findall(str(text or ""))) >= 2 else "en"
