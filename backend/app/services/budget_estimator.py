"""Project-out a drama's budget before it is generated.

Two numbers the create flow headlines:
- credit_usd: what the video / image / voice generation will cost (the real cap
  on how much film you can make).
- llm_tokens: the LLM tokens the pipeline burns writing + boarding + crafting —
  the hackathon's judged allowance.

Estimates are rough but CALIBRATED against real production ledgers: a
completed 40s full-auto drama (4 scenes, 8 shots, 4 characters) burned 76K
LLM tokens — continuity vision scoring 39K, prompt craft 14K, storyboard and
set dressing 9K, casting 8K, script 6K — and $4.32 of video. The per-unit
constants below reproduce that ledger; they scale with scope so the user sees
the true shape of the spend.
"""
from app.services.cost_rates import RATES

# scope model — one short scene per ~15s, an adaptive clip averages ~6s
_SECONDS_PER_SCENE = 15
_AVG_CLIP_SECONDS = 6
# generation blend the allocator tends toward under a normal budget
_WAN_SHARE = 0.4
# the audio-first fitter grows speaking shots to hold their dialogue, and a
# flagged take occasionally re-renders — billed footage runs past the target
_FOOTAGE_OVERAGE = 1.15

# per-unit LLM token cost (input+output combined), measured from the ledger
_TOK = {
    "per_episode": 6000,    # write + structure + judge one screenplay
    "per_project": 8000,    # cast extraction, relationships, wardrobe, style, clarify, title
    "per_scene": 2200,      # board a scene + set dressing
    "per_shot": 6600,       # prompt craft (~1.7K) + continuity vision scoring (~4.9K)
    "per_character": 800,   # face / appearance profiling
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

    # video: blended wan/happyhorse per-second rate across the clip seconds,
    # plus the dialogue-fitting and retry overage real runs show
    per_sec = (_WAN_SHARE * RATES["video_wan_per_sec"]
               + (1 - _WAN_SHARE) * RATES["video_hh_per_sec"])
    video_usd = scope["video_seconds"] * _FOOTAGE_OVERAGE * per_sec

    # images: 1 face + ~2 outfits per character, 1 plate per scene, 1 style plate
    image_count = chars * 3 + scope["scenes"] + 1
    image_usd = image_count * RATES["image_per_item"]

    # tts: ~90 spoken characters per shot that talks (~70% of shots)
    tts_chars = int(scope["shots"] * 0.7 * 90)
    tts_usd = (tts_chars / 10_000) * RATES["tts_per_10k_chars"]

    credit_usd = round(video_usd + image_usd + tts_usd, 2)

    llm_tokens = (
        scope["episodes"] * _TOK["per_episode"]
        + _TOK["per_project"]
        + scope["scenes"] * _TOK["per_scene"]
        + scope["shots"] * _TOK["per_shot"]
        + chars * _TOK["per_character"]
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
