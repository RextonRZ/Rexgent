from app.director.recommender import recommend_look
from app.director.types import LookProfile


def test_known_genre_maps_to_look():
    look = recommend_look("thriller")
    assert isinstance(look, LookProfile)
    assert look.lens_bias == "85mm" and look.colour_mood == "COOL"


def test_unknown_genre_neutral_default_no_raise():
    look = recommend_look(None)
    assert look.lighting == "NATURAL" and look.lens_bias == "50mm"
