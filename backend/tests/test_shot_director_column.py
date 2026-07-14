from app.models.shot import Shot


def test_shot_has_director_json_column():
    cols = Shot.__table__.columns.keys()
    assert "director_json" in cols
