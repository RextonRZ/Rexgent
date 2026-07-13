from app.services.model_measurement import summarize, pick_winner, format_scorecard


def test_summarize_means_and_count():
    clips = [
        {"face_score": 0.6, "outfit_score": 0.8, "consistency_score": 70},
        {"face_score": 0.8, "outfit_score": 0.6, "consistency_score": 80},
    ]
    s = summarize(clips)
    assert s["n"] == 2
    assert s["mean_face"] == 0.7
    assert s["mean_outfit"] == 0.7
    assert s["mean_continuity"] == 75.0


def test_summarize_ignores_none_scores():
    clips = [
        {"face_score": None, "outfit_score": 0.8, "consistency_score": 70},
        {"face_score": 0.8, "outfit_score": None, "consistency_score": None},
    ]
    s = summarize(clips)
    assert s["mean_face"] == 0.8
    assert s["mean_outfit"] == 0.8
    assert s["mean_continuity"] == 70.0
    assert s["n"] == 2


def test_summarize_empty():
    s = summarize([])
    assert s == {"n": 0, "mean_face": None, "mean_outfit": None, "mean_continuity": None}


def test_pick_winner_by_mean_face():
    results = [
        {"config": "happyhorse", "mean_face": 0.72, "mean_continuity": 67},
        {"config": "wan", "mean_face": 0.46, "mean_continuity": 46},
    ]
    assert pick_winner(results) == "happyhorse"


def test_pick_winner_tiebreaks_on_continuity():
    results = [
        {"config": "happyhorse", "mean_face": 0.6, "mean_continuity": 70},
        {"config": "wan", "mean_face": 0.6, "mean_continuity": 65},
    ]
    assert pick_winner(results) == "happyhorse"


def test_pick_winner_ignores_configs_with_no_face():
    results = [
        {"config": "happyhorse", "mean_face": None, "mean_continuity": None},
        {"config": "wan", "mean_face": 0.5, "mean_continuity": 55},
    ]
    assert pick_winner(results) == "wan"


def test_pick_winner_none_when_no_data():
    assert pick_winner([{"config": "wan", "mean_face": None, "mean_continuity": None}]) is None


def test_format_scorecard_contains_configs_and_winner():
    results = [
        {"config": "happyhorse", "n": 3, "mean_face": 0.72, "mean_outfit": 0.7, "mean_continuity": 67},
        {"config": "wan", "n": 3, "mean_face": 0.46, "mean_outfit": 0.5, "mean_continuity": 46},
    ]
    out = format_scorecard(results)
    assert "happyhorse" in out and "wan" in out
    assert "0.72" in out and "0.46" in out
    assert "WINNER" in out.upper()
