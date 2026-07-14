from app.services.lipsync import pick_lipsync_line, speaker_matches, lipsync_media


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


def test_speaker_must_be_the_only_visible_character():
    line = {"character_name": "IM SOL"}
    assert speaker_matches(line, ["IM SOL"], []) is True
    # case-insensitive
    assert speaker_matches({"character_name": "im sol"}, ["IM SOL"], []) is True
    # two visible people -> no
    assert speaker_matches(line, ["IM SOL", "RYU SUN-JAE"], []) is False
    # the other person is a foreground occluder (face unseen) -> yes
    assert speaker_matches(line, ["IM SOL", "RYU SUN-JAE"], ["RYU SUN-JAE"]) is True
    # the visible person is NOT the speaker -> no
    assert speaker_matches(line, ["RYU SUN-JAE"], []) is False
    # nobody visible -> no
    assert speaker_matches(line, ["RYU SUN-JAE"], ["RYU SUN-JAE"]) is False


def test_lipsync_media_shape():
    media = lipsync_media("https://oss/frame.jpg", "https://oss/l0.wav")
    assert media == [
        {"type": "first_frame", "url": "https://oss/frame.jpg"},
        {"type": "driving_audio", "url": "https://oss/l0.wav"},
    ]


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
