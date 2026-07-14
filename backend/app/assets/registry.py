"""The Asset Library structure, declared in ONE place so it is extensible and
nothing is hardcoded elsewhere. Add a type or category = edit this file."""

ASSET_TYPES: dict[str, list[str]] = {
    "music": ["romance", "sadness", "happy", "comedy", "action", "thriller",
              "horror", "luxury", "daily", "inspirational", "fantasy", "historical"],
    "sfx": ["door", "phone", "footsteps", "vehicle", "weather", "fight",
            "human", "ui", "magic", "explosion"],
    "ambience": ["rain", "forest", "night", "city", "office", "hospital",
                 "classroom", "restaurant", "cafe", "airport", "subway",
                 "courtroom", "beach", "wedding", "mall"],
    "vfx": ["fire", "smoke", "explosion", "magic", "lightning", "blood",
            "spark", "dust", "snow", "rain", "fog"],
    "transitions": ["fade", "crossfade", "zoom", "blur", "whip", "flash",
                    "glitch", "camera_shake", "film_cut"],
    "overlays": ["film_grain", "dust", "light_leak", "vhs", "cctv",
                 "security_camera", "old_tv", "rain_overlay", "snow_overlay"],
    "subtitles": ["netflix", "tiktok", "youtube", "anime", "minimal",
                  "modern", "comic"],
    "fonts": ["display", "body", "handwritten", "mono"],
    "luts": ["warm", "cold", "romantic", "horror", "thriller", "dream",
             "cinematic", "vintage", "anime"],
    "stickers": ["emoji", "arrow", "callout", "meme"],
    "templates": ["office_romance", "ceo_drama", "campus", "hospital",
                  "fantasy", "ancient_china", "sci_fi", "police", "mafia"],
}


def categories_for(asset_type: str) -> list[str]:
    """The declared categories for a type, or [] for an unknown type."""
    return list(ASSET_TYPES.get(asset_type, []))
