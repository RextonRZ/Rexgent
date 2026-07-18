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


def test_detect_language_reads_cjk_scripts_as_zh():
    from app.services.language import detect_language
    assert detect_language("小雨在花园里寻找她的兔子") == "zh"
    # a zh screenplay keeps English format markers; the prose decides
    assert detect_language("INT. 卧室 - 夜晚\n小雨哭着抱住兔子") == "zh"


def test_detect_language_defaults_to_en():
    from app.services.language import detect_language
    assert detect_language("A girl searches the garden for her rabbit") == "en"
    assert detect_language("") == "en"
    assert detect_language(None) == "en"
