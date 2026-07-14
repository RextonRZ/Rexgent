from app.services.lipsync import pick_lipsync_line


LINES = [
    {"audio_url": "https://oss/l0.wav", "character_name": "IM SOL"},
    {"audio_url": "https://oss/l1.wav", "character_name": "RYU SUN-JAE"},
]


def test_kth_speaking_shot_gets_kth_line():
    # the same convention place_dialogue uses: k-th line -> k-th speaking shot
    assert pick_lipsync_line("s2", ["s1", "s2"], LINES) == LINES[1]


def test_non_speaking_shot_gets_nothing():
    assert pick_lipsync_line("sX", ["s1", "s2"], LINES) is None


def test_shot_beyond_the_lines_gets_nothing():
    assert pick_lipsync_line("s2", ["s1", "s2"], LINES[:1]) is None


def test_folded_overflow_shot_is_ineligible():
    # 3 lines, 2 speaking shots: the LAST speaking shot carries lines 1 AND 2
    # at placement — a mouth can't be driven by two lines, so no lip-sync
    three = LINES + [{"audio_url": "https://oss/l2.wav", "character_name": "IM SOL"}]
    assert pick_lipsync_line("s2", ["s1", "s2"], three) is None
    # the first shot still speaks exactly one line
    assert pick_lipsync_line("s1", ["s1", "s2"], three) == three[0]


def test_pick_matches_by_dialogue_text_not_position():
    lines = [
        {"character_name": "THE STRANGER", "text": "You can run, but you can't hide.", "audio_url": "a", "duration": 3.0},
        {"character_name": "MIAO JING", "text": "Chen Yi, please, trust me.", "audio_url": "b", "duration": 2.0},
    ]
    speaking = ["shotA", "shotB"]
    got = pick_lipsync_line("shotB", speaking, lines,
                            shot_dialogue="You can run, but you can't hide.")
    assert got["character_name"] == "THE STRANGER"


def test_pick_falls_back_to_position_without_dialogue():
    lines = [{"character_name": "A", "text": "hi", "audio_url": "a", "duration": 1.0}]
    assert pick_lipsync_line("s1", ["s1"], lines)["character_name"] == "A"


def test_pick_resolves_speaker_without_audio_url():
    # native-talk sources scene_lines straight from the SCRIPT (character + line),
    # with NO synthesized audio_url — the speaker must still resolve by text so the
    # right mouth moves even though nothing was ever synthesized.
    lines = [
        {"character_name": "A", "text": "Stop right there."},
        {"character_name": "B", "text": "You lied to me."},
    ]
    got = pick_lipsync_line("s2", ["s1", "s2"], lines,
                            shot_dialogue="You lied to me.")
    assert got is not None and got["character_name"] == "B"
