

def test_defer_hair_to_image_replaces_length_keeps_accessories():
    # the plate is the boss: textual "chin-length" must give way to the
    # reference image, while accessory / facial-hair pins survive
    from app.mcp_tools.scene_prompt_craft import _defer_hair_to_image, _HAIR_DEFER
    out = _defer_hair_to_image({
        "video_prompt_fragment": ("a 10-year-old girl, chin-length straight "
                                   "black hair with blunt bangs, no hair "
                                   "accessories, light-olive skin")})
    frag = out["video_prompt_fragment"]
    assert "chin-length" not in frag
    assert _HAIR_DEFER in frag
    assert "no hair accessories" in frag
    assert "light-olive skin" in frag


def test_defer_hair_to_image_handles_chinese_and_strings():
    from app.mcp_tools.scene_prompt_craft import _defer_hair_to_image, _HAIR_DEFER
    out = _defer_hair_to_image("十岁女孩，齐肩长发，中分刘海，蓝色连衣裙")
    assert "长发" not in out and "刘海" not in out
    assert _HAIR_DEFER in out
    assert "蓝色连衣裙" in out
