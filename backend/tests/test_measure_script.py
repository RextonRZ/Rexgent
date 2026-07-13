import backend_scripts_measure as m


def test_configs_are_the_two_anchor_models():
    assert m.CONFIGS == ["happyhorse", "wan"]


def test_collect_clip_scores_shapes_rows():
    class C:
        def __init__(self, f, o, s):
            self.face_score, self.outfit_score, self.consistency_score = f, o, s
    rows = m.collect_clip_scores([C(0.7, 0.8, 70), C(0.6, 0.6, 60)])
    assert rows == [
        {"face_score": 0.7, "outfit_score": 0.8, "consistency_score": 70},
        {"face_score": 0.6, "outfit_score": 0.6, "consistency_score": 60}]
