from types import SimpleNamespace
from app.services.character_traits import (is_creature, is_stylized_style,
                                           species_of)


def test_species_of_finds_the_creature_noun():
    assert species_of("a small white rabbit with one grey ear") == "rabbit"
    assert species_of("an old golden retriever dog, muddy paws") == "dog"
    assert species_of("a battered service robot with one cracked lens") == "robot"


def test_species_of_ignores_humans_and_incidental_words():
    assert species_of("a tall woman in a red coat, sharp eyes") is None
    # "cat-like reflexes" describes a person, not a cat
    assert species_of("a wiry man with cat-like reflexes") is None
    assert species_of("") is None
    assert species_of(None) is None


def test_is_creature_reads_descriptions_not_the_name():
    # a HUMAN nicknamed Bear must not be cast as an animal
    human = SimpleNamespace(name="Bear", physical_description="a broad man in his 40s",
                            visual_description=None, role="SUPPORTING")
    assert is_creature(human) is False
    rabbit = SimpleNamespace(name="Snowy",
                             physical_description="a small white rabbit, red collar",
                             visual_description=None, role="SUPPORTING")
    assert is_creature(rabbit) is True


def test_species_of_finds_chinese_creature_nouns():
    # a zh run writes physical_description in Chinese ("一只白色的小狗"), so the
    # English-only matcher never fired and a pet was mis-cast as a human
    assert species_of("一只毛茸茸的白色小狗，戴着红色项圈") == "狗"
    assert species_of("一只橘色的猫咪，绿眼睛") == "猫"
    assert species_of("安吉琳心爱的宠物，一只雪白的小兔子") in ("宠物", "兔子", "兔")


def test_species_of_ignores_chinese_lookalike_words():
    # 象征 (symbolize) must not read as 象 (elephant); 马上 (at once) not 马
    # (horse); 马虎 (careless) not 虎 (tiger); 牛仔 (cowboy) not 牛 (cow)
    assert species_of("它的存在象征着童真，马上就会出现") is None
    assert species_of("一个做事马虎、穿着牛仔裤的年轻人") is None
    assert species_of("一位四十多岁、身材宽阔的男人") is None


def test_is_creature_reads_a_chinese_pet_description():
    # 雪球 (Snowball): a named pet described in Chinese
    xueqiu = SimpleNamespace(name="雪球",
                             physical_description="一只蓬松的白色小狗，安吉琳的宠物",
                             visual_description=None, role="SUPPORTING")
    assert is_creature(xueqiu) is True


def test_is_stylized_style_flags_non_photoreal_looks():
    assert is_stylized_style("2D anime, cel shaded, vibrant") is True
    assert is_stylized_style("pixel art retro game style") is True
    assert is_stylized_style("3D Pixar style cartoon") is True
    assert is_stylized_style("cinematic realistic drama") is False
    assert is_stylized_style("", None) is False


def test_is_stylized_style_flags_3d_and_cgi_without_a_brand_name():
    # style_plate.txt strips IP names (pixar, ghibli) into generic phrasing,
    # so the generic 3D/CGI vocabulary must flip stylized mode on its own
    assert is_stylized_style("3d animated feature, soft global illumination") is True
    assert is_stylized_style("stylized CGI characters, rounded features") is True
    assert is_stylized_style("realistic drama shot in 163 days") is False
