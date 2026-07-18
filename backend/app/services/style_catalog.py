"""The visual-style catalog behind the create-drama style picker.

Each entry maps a canonical picker key to the free-text seed that primes
style_from_request (and, through it, the style plate and every costume
plate). Every seed keeps its catalog key inside the text so
is_stylized_style always recognizes the look even before the LLM expands
it. Photoreal is the absence of a key: seed_for returns None and the
pipeline falls back to its usual "cinematic realistic drama" default.
"""

STYLE_SEEDS: dict[str, str] = {
    "cartoon": "cartoon style animated drama, bold clean outlines, flat vivid colors, exaggerated expressions",
    "anime": "anime style 2D animation, clean line art, large expressive eyes, cel shading, vivid palette",
    "manga": "manga style monochrome illustration, ink line art, screentone shading, dramatic composition",
    "cel-shaded": "cel-shaded animation look, hard two-tone shadows, crisp dark outlines, saturated colors",
    "2d": "2d flat animation style, simple graphic shapes, bold color blocking, minimal shading",
    "pixel": "pixel art style, chunky visible pixels, limited color palette, retro game look",
    "8-bit": "8-bit pixel art style, blocky low resolution sprites, tiny palette, retro console look",
    "16-bit": "16-bit pixel art style, detailed sprites, dithered shading, golden era console look",
    "claymation": "claymation style, sculpted clay characters, visible fingerprint texture, handmade sets",
    "stop-motion": "stop-motion puppet animation style, handcrafted miniature sets, tactile fabric and wood textures",
    "comic": "comic book style, inked outlines, halftone dot shading, dynamic high-contrast panels",
    "illustrated": "illustrated storybook style, painterly textures, soft edges, warm picture book light",
    "hand-drawn": "hand-drawn animation style, visible pencil linework, organic wobble, sketchbook charm",
    "watercolor": "watercolor painting style, soft bleeding washes, paper grain texture, gentle gradients",
    "sketch": "sketch style, rough pencil strokes, crosshatched shading, unfinished paper drawing look",
    "low-poly": "low-poly 3d style, faceted geometric surfaces, flat shaded polygons, minimalist forms",
    "voxel": "voxel art style, 3d cube blocks, isometric charm, chunky stepped geometry",
    "chibi": "chibi anime style, tiny bodies with oversized heads, big eyes, cute rounded features",
    "ghibli": "ghibli inspired hand-painted animation style, lush natural backgrounds, soft warm light",
    "pixar": "pixar style 3d animated feature look, expressive stylized characters, soft global illumination",
    "disney": "disney style animated feature look, expressive charming characters, polished fairytale lighting",
}

_PHOTOREAL = {"photoreal", "photorealistic", "realistic", "cinematic", "real", "none"}


def normalize_style(value) -> str:
    """Lowercase, trimmed, spaces/underscores as hyphens: "Stop Motion" -> "stop-motion"."""
    return str(value or "").strip().lower().replace("_", "-").replace(" ", "-")


def catalog_key(value) -> str | None:
    """The canonical catalog key for a picker value, or None for photoreal
    and anything the catalog doesn't know."""
    key = normalize_style(value)
    return key if key in STYLE_SEEDS else None


def seed_for(value) -> str | None:
    """The style seed text for a picker value, or None for photoreal/unknown."""
    key = catalog_key(value)
    return STYLE_SEEDS[key] if key else None


def style_seed_text(free_text, visual_style) -> str:
    """The text that primes style_from_request: an existing StylePreset
    free_text always wins (the LLM-expanded prompt from a previous run keeps
    plates consistent across reruns), then the picker seed, then photoreal."""
    existing = str(free_text or "").strip()
    if existing:
        return existing
    return seed_for(visual_style) or "cinematic realistic drama"
