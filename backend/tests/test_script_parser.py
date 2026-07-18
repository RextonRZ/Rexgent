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


def test_parse_markdown_and_fountain_as_text():
    parser = ScriptParser()
    for name in ("script.md", "script.fountain"):
        result = parser.parse_bytes("INT. 咖啡馆 - 夜\n\n对白在这里。".encode("utf-8"), name)
        assert "咖啡馆" in result, name


def test_legacy_doc_gets_a_clear_error():
    # python-docx only reads the zip-based .docx; a real Word 97 file used to
    # crash the request with an opaque 500
    parser = ScriptParser()
    with pytest.raises(ValueError, match="docx or PDF"):
        parser.parse_bytes(b"\xd0\xcf\x11\xe0legacy word bytes", "old.doc")


def test_scanned_pdf_gets_a_clear_error(monkeypatch):
    # an image-only PDF extracts (nearly) no text and used to "succeed" into
    # a 0-scene structure with no explanation
    parser = ScriptParser()
    monkeypatch.setattr(ScriptParser, "_extract_pdf_text",
                        lambda self, data: "   \n  \n")
    with pytest.raises(ValueError, match="selectable text"):
        parser.parse_bytes(b"%PDF-1.4 fake", "scan.pdf")
