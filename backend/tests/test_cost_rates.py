from app.services.cost_rates import video_cost, image_cost, tts_cost, llm_cost


def test_video_cost():
    assert video_cost(5, "wan") == 0.75
    assert round(video_cost(5, "happyhorse"), 3) == 0.54


def test_wan_r2v_bills_at_wan_rate():
    # wan_r2v is a Wan mode — it must bill at the Wan per-second rate, not the
    # cheaper happyhorse rate
    assert video_cost(5, "wan_r2v") == video_cost(5, "wan") == 0.75


def test_videoedit_bills_at_wan_rate():
    # wan2.7-videoedit (the repair ladder's patch pass) is a Wan mode — it bills
    # at the Wan per-second rate, not the cheaper happyhorse rate
    assert video_cost(10, "videoedit") == video_cost(10, "wan") == 1.5


def test_image_and_tts_and_llm():
    assert image_cost(2) == 0.15
    assert tts_cost(10000) == 0.13
    assert round(llm_cost(1000, 1000), 4) == round(0.0016 + 0.0064, 4)
