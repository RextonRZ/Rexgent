from app.services.character_traits import is_stylized_style
from app.services.style_catalog import (
    STYLE_SEEDS,
    catalog_key,
    seed_for,
    style_seed_text,
)


def test_every_catalog_entry_reads_as_stylized():
    # the whole point of the picker: choosing any catalog look must flip
    # stylized mode (ArcFace skip) — both via the seed text and the raw key
    for key, seed in STYLE_SEEDS.items():
        assert is_stylized_style(seed), f"seed for {key} lacks a trigger word"
        assert is_stylized_style(key), f"key {key} is not itself a trigger"


def test_seed_for_normalizes_case_spacing_and_underscores():
    assert seed_for("PIXAR") == STYLE_SEEDS["pixar"]
    assert seed_for("Stop Motion") == STYLE_SEEDS["stop-motion"]
    assert seed_for("8 bit") == STYLE_SEEDS["8-bit"]
    assert seed_for("cel_shaded") == STYLE_SEEDS["cel-shaded"]


def test_seed_for_photoreal_and_unknown_are_none():
    for value in (None, "", "  ", "photoreal", "realistic", "cinematic",
                  "vaporwave-dreams"):
        assert seed_for(value) is None, value


def test_catalog_key_returns_canonical_key_or_none():
    assert catalog_key("Stop Motion") == "stop-motion"
    assert catalog_key("ghibli") == "ghibli"
    assert catalog_key("photoreal") is None
    assert catalog_key("nonsense") is None
    assert catalog_key(None) is None


def test_style_seed_text_prefers_existing_then_seed_then_default():
    # an LLM-expanded free_text from a previous run always wins (plate
    # consistency); the picker seed fills first runs; photoreal falls back
    assert style_seed_text("noir alley look", "pixar") == "noir alley look"
    assert style_seed_text("", "pixar") == STYLE_SEEDS["pixar"]
    assert style_seed_text("   ", "photoreal") == "cinematic realistic drama"
    assert style_seed_text(None, None) == "cinematic realistic drama"
