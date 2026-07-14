from app.services.caption_generator import CaptionGenerator


def test_captions_come_from_shot_dialogue_without_tts():
    cut = [{"dialogue": "Stop right there.", "duration": 4.0},
           {"dialogue": None, "duration": 2.0},
           {"dialogue": "You lied to me.", "duration": 5.0}]
    srt = CaptionGenerator().generate_srt(cut)
    assert "Stop right there." in srt and "You lied to me." in srt
    assert srt.count("-->") == 2
