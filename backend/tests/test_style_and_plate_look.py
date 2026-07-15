"""Reference plates must be emotionally NEUTRAL: HappyHorse r2v copies the
reference face, expression included, so a smiling/angry plate bleeds that mood
into every shot that references it and fights the shot's real emotional beat.
Per-shot emotion belongs in the video prompt, not the plate.

And the style plate should follow the Director's genre look, so the two style
channels (style-plate image + per-shot stylization) don't diverge."""
from app.services.plate_generator import (character_plate_prompt, clean_appearance,
                                          subject_descriptor)
from app.services.casting_director import style_look_clause
from app.director.recommender import recommend_look

# the real description that made the plate render a woman clutching a framed photo
_SCENE_DESC = "Soaked, trembling, eyes red from crying, clutching a small photo in her hand."


def test_clean_appearance_drops_scene_moments():
    out = clean_appearance(_SCENE_DESC).lower()
    for weird in ("photo", "crying", "soaked", "clutching", "trembling"):
        assert weird not in out, out


def test_clean_appearance_keeps_real_looks():
    out = clean_appearance("rounded face, soft cheekbones, almond eyes, dark bob hair")
    assert "rounded face" in out and "almond eyes" in out and "dark bob hair" in out


def test_subject_descriptor_strips_props_but_keeps_identity():
    s = subject_descriptor("female", "late 40s", _SCENE_DESC).lower()
    assert "photo" not in s and "crying" not in s and "soaked" not in s
    assert "woman" in s  # still names who it is


def test_character_plate_prompt_asks_for_neutral_expression():
    # every branch (face/no-face, outfit/no-outfit) must carry the neutral cue
    for has_face in (True, False):
        for outfit in ("a grey wool coat", ""):
            p = character_plate_prompt(has_face, "a 30-year-old man", outfit=outfit).lower()
            assert "neutral" in p and "expression" in p, p


def test_style_look_clause_reflects_director_genre_look():
    look = recommend_look("thriller")
    clause = style_look_clause("thriller")
    assert look.stylization in clause
    assert look.lighting in clause
    assert look.colour_mood in clause


def test_style_look_clause_never_raises_on_unknown_genre():
    clause = style_look_clause("zzz-not-a-real-genre")
    assert isinstance(clause, str) and clause.strip()
