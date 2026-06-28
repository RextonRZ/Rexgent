import pytest
from app.services.script_parser import ScriptParser


def test_parse_txt():
    parser = ScriptParser()
    result = parser.parse_bytes(b"INT. OFFICE - DAY\n\nYUKI sits at her desk.", "test.txt")
    assert "INT. OFFICE" in result
    assert "YUKI" in result


def test_parse_txt_unicode():
    parser = ScriptParser()
    result = parser.parse_bytes("INT. CAFÉ - NIGHT\n\nDialogue here.".encode("utf-8"), "script.txt")
    assert "CAFÉ" in result


def test_parse_unsupported_format():
    parser = ScriptParser()
    with pytest.raises(ValueError, match="Unsupported"):
        parser.parse_bytes(b"data", "test.xyz")


def test_parse_no_extension():
    parser = ScriptParser()
    with pytest.raises(ValueError, match="Unsupported"):
        parser.parse_bytes(b"data", "noextension")
