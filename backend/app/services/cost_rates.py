RATES = {
    "video_wan_per_sec": 0.15,
    "video_hh_per_sec": 0.108,
    "image_per_item": 0.075,
    "tts_per_10k_chars": 0.13,
    "llm_in_per_1k": 0.0016,
    "llm_out_per_1k": 0.0064,
}


def video_cost(seconds: float, model: str) -> float:
    # wan_r2v (reference-to-video) and videoedit (wan2.7-videoedit, the repair
    # ladder's patch pass) are both Wan modes — they bill at the Wan rate, not
    # the cheaper happyhorse rate
    rate = (RATES["video_wan_per_sec"] if model in ("wan", "wan_r2v", "videoedit")
            else RATES["video_hh_per_sec"])
    return round(seconds * rate, 4)


def image_cost(n: int = 1) -> float:
    return round(n * RATES["image_per_item"], 4)


def tts_cost(chars: int) -> float:
    return round((chars / 10_000) * RATES["tts_per_10k_chars"], 4)


def llm_cost(in_tokens: int, out_tokens: int) -> float:
    return round((in_tokens / 1000) * RATES["llm_in_per_1k"]
                 + (out_tokens / 1000) * RATES["llm_out_per_1k"], 4)
