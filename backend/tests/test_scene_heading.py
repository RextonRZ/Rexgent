from app.services.scene_heading import infer_setting, normalize_scene_headings


def _scene(n, heading, location, time="NIGHT"):
    return {"scene_number": n, "heading": heading, "location": location,
            "time_of_day": time}


def test_street_tagged_int_becomes_ext():
    # the user's exact bug: a street labelled INT.
    s = normalize_scene_headings({"scenes": [
        _scene(1, "INT. 边境冬夜城 - 夜晚 - 街道", "边境冬夜城街道"),
    ]})["scenes"][0]
    assert s["heading"].startswith("EXT.")
    assert s["setting_type"] == "exterior"


def test_alley_is_exterior():
    s = normalize_scene_headings({"scenes": [
        _scene(2, "INT. 小巷 - 夜晚", "小巷"),
    ]})["scenes"][0]
    assert s["heading"].startswith("EXT.")


def test_hut_stays_interior():
    s = normalize_scene_headings({"scenes": [
        _scene(3, "INT. 废弃小屋 - 夜晚", "废弃小屋"),
    ]})["scenes"][0]
    assert s["heading"].startswith("INT.")
    assert s["setting_type"] == "interior"


def test_same_location_gets_one_consistent_prefix():
    # scenes 1 and 4 are the SAME street; one said INT, the other EXT
    scenes = normalize_scene_headings({"scenes": [
        _scene(1, "INT. 边境冬夜城 - 夜晚 - 街道", "边境冬夜城街道"),
        _scene(4, "EXT. 边境冬夜城 - 夜晚 - 街道", "边境冬夜城街道"),
    ]})["scenes"]
    prefixes = {s["heading"].split()[0] for s in scenes}
    assert prefixes == {"EXT."}


def test_rooftop_beats_the_indoor_word_it_contains():
    # 屋顶 (rooftop) contains 屋 (room) — outdoor must win
    assert infer_setting("屋顶 - 夜晚") == "exterior"
    assert infer_setting("rooftop chase") == "exterior"


def test_english_words_match_whole_words_only():
    # "roof" must not fire inside "roofless"? boundary check with "cell"/"cellar"
    assert infer_setting("the excellent view") is None


def test_unknown_location_keeps_the_llm_prefix():
    s = normalize_scene_headings({"scenes": [
        _scene(5, "EXT. 无名之地 - 黄昏", "无名之地"),
    ]})["scenes"][0]
    assert s["heading"].startswith("EXT.")
    assert s["setting_type"] == "exterior"


def test_missing_heading_rebuilt_from_location():
    s = normalize_scene_headings({"scenes": [
        _scene(6, "", "废弃小屋"),
    ]})["scenes"][0]
    assert s["heading"] == "INT. 废弃小屋 - NIGHT"


def test_no_scenes_is_safe():
    assert normalize_scene_headings({}) == {}
