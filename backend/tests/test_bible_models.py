from app.models.costume_variant import CostumeVariant
from app.models.location_plate import LocationPlate
from app.models.style_preset import StylePreset


def test_costume_variant_columns():
    cols = CostumeVariant.__table__.columns.keys()
    for c in ["id", "character_id", "label", "outfit_description",
              "plate_image_url", "face_vector", "scene_numbers", "is_default", "plate_status"]:
        assert c in cols


def test_location_plate_columns():
    cols = LocationPlate.__table__.columns.keys()
    for c in ["id", "project_id", "location_key", "description", "plate_image_url", "scene_numbers"]:
        assert c in cols


def test_style_preset_columns():
    cols = StylePreset.__table__.columns.keys()
    for c in ["id", "project_id", "style_tags", "free_text", "plate_image_url", "negative_prompt"]:
        assert c in cols
