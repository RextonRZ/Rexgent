"""Project-out a drama's budget before it is generated.

Two numbers the create flow headlines:
- credit_usd: what the video / image / voice generation will cost (the real cap
  on how much film you can make).
- llm_tokens: the LLM tokens the pipeline burns writing + boarding + crafting —
  the hackathon's judged allowance.

Estimates are deliberately rough; they scale with the drama's scope so the user
sees the shape of the spend, not an exact invoice.
"""
from app.services.cost_rates import RATES

# scope model — one short scene per ~15s, an adaptive clip averages ~6s
_SECONDS_PER_SCENE = 15
_AVG_CLIP_SECONDS = 6
# generation blend the allocator tends toward under a normal budget
_WAN_SHARE = 0.4

# per-unit LLM token cost (input+output combined, rough)
_TOK = {
    "script_per_episode": 3200,     # generate + judge a screenplay
    "characters": 2000,             # extract cast + relationships once
    "storyboard_per_scene": 1500,   # board a scene
    "prompt_craft_per_shot": 800,   # craft each video prompt
}


def estimate_scope(episode_count: int, target_length: int) -> dict:
    episodes = max(1, episode_count)
    seconds = max(5, target_length)
    total_seconds = episodes * seconds
    scenes = max(episodes, round(total_seconds / _SECONDS_PER_SCENE))
    shots = max(scenes, round(total_seconds / _AVG_CLIP_SECONDS))
    return {"episodes": episodes, "scenes": scenes, "shots": shots,
            "video_seconds": total_seconds}


def estimate_budget(episode_count: int, target_length: int, characters: int = 4) -> dict:
    scope = estimate_scope(episode_count, target_length)
    chars = max(1, characters)

    # video: blended wan/happyhorse per-second rate across the clip seconds
    per_sec = (_WAN_SHARE * RATES["video_wan_per_sec"]
               + (1 - _WAN_SHARE) * RATES["video_hh_per_sec"])
    video_usd = scope["video_seconds"] * per_sec

    # images: 1 face + ~2 outfits per character, 1 plate per scene, 1 style plate
    image_count = chars * 3 + scope["scenes"] + 1
    image_usd = image_count * RATES["image_per_item"]

    # tts: ~90 spoken characters per shot that talks (~70% of shots)
    tts_chars = int(scope["shots"] * 0.7 * 90)
    tts_usd = (tts_chars / 10_000) * RATES["tts_per_10k_chars"]

    credit_usd = round(video_usd + image_usd + tts_usd, 2)

    llm_tokens = (
        scope["episodes"] * _TOK["script_per_episode"]
        + _TOK["characters"]
        + scope["scenes"] * _TOK["storyboard_per_scene"]
        + scope["shots"] * _TOK["prompt_craft_per_shot"]
    )

    return {
        "scope": scope,
        "credit_usd": credit_usd,
        "credit_breakdown": {
            "video": round(video_usd, 2),
            "image": round(image_usd, 2),
            "tts": round(tts_usd, 2),
        },
        "llm_tokens": int(llm_tokens),
    }
