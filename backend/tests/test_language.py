from app.services.script_generator import ScriptGenerator
from app.services.language import language_instruction


def test_language_instruction_zh():
    instr = language_instruction("zh")
    assert "Chinese" in instr or "中文" in instr


def test_language_instruction_en_default():
    assert language_instruction("en") == ""


def test_language_instruction_unknown_is_empty():
    assert language_instruction("fr") == ""


def test_script_generator_exposes_helper():
    gen = ScriptGenerator.__new__(ScriptGenerator)
    assert gen.language_instruction("zh") != ""
    assert gen.language_instruction("en") == ""
