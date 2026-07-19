import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.plate_generator import PlateGenerator


@pytest.mark.asyncio
async def test_generate_and_store_plate_character_embeds_face():
    gen = PlateGenerator.__new__(PlateGenerator)
    gen.qwen = MagicMock()
    gen.qwen.generate_image = AsyncMock(return_value="https://img/raw.png")
    gen.oss = MagicMock()
    gen.oss.get_project_path = MagicMock(return_value="proj/plates/x.png")
    gen.oss.upload_bytes = MagicMock(return_value="https://oss/x.png")
    gen._fetch_bytes = MagicMock(return_value=b"imgbytes")
    gen.embedder = MagicMock()
    gen.embedder.extract = AsyncMock(return_value={"vector": [0.1] * 512, "description": {}})

    url, vector = await gen.generate_and_store_plate(
        project_id="p1", kind="character", key="Mia:uniform", prompt="navy uniform portrait")
    assert url == "https://oss/x.png"
    assert vector == [0.1] * 512
    # embedded the SAME bytes we uploaded (single download, no second fetch)
    gen.embedder.extract.assert_awaited_once()
    assert gen.embedder.extract.call_args.kwargs["image_bytes"] == b"imgbytes"


@pytest.mark.asyncio
async def test_generate_and_store_plate_location_skips_face():
    gen = PlateGenerator.__new__(PlateGenerator)
    gen.qwen = MagicMock()
    gen.qwen.generate_image = AsyncMock(return_value="https://img/raw.png")
    gen.oss = MagicMock()
    gen.oss.get_project_path = MagicMock(return_value="proj/plates/x.png")
    gen.oss.upload_bytes = MagicMock(return_value="https://oss/loc.png")
    gen._fetch_bytes = MagicMock(return_value=b"imgbytes")
    gen.embedder = MagicMock()
    gen.embedder.extract = AsyncMock()

    url, vector = await gen.generate_and_store_plate(
        project_id="p1", kind="location", key="coffee_shop", prompt="cozy cafe")
    assert url == "https://oss/loc.png"
    assert vector is None
    gen.embedder.extract.assert_not_called()


def test_subject_descriptor_keeps_numeric_age_without_gender():
    from app.services.plate_generator import subject_descriptor
    # gender missing but age '20s' — must still anchor a human adult, or the
    # model reads 'soft/delicate' face text as a child
    s = subject_descriptor(None, "20s", "soft, delicate features")
    assert s.startswith("a person around 20s")
    # non-numeric 'age' with no gender (e.g. a pet) keeps appearance-only
    dog = subject_descriptor("unknown", "dog age", "small white dog")
    assert dog == "small white dog"


@pytest.mark.asyncio
async def test_character_plate_edits_face_when_reference_given():
    gen = PlateGenerator.__new__(PlateGenerator)
    gen.qwen = MagicMock()
    gen.qwen.generate_image = AsyncMock(return_value="https://img/text.png")
    gen.qwen.edit_image = AsyncMock(return_value="https://img/edited.png")
    gen.oss = MagicMock()
    gen.oss.get_project_path = MagicMock(return_value="proj/plates/x.png")
    gen.oss.upload_bytes = MagicMock(return_value="https://oss/x.png")
    gen._fetch_bytes = MagicMock(return_value=b"imgbytes")
    gen.embedder = MagicMock()
    gen.embedder.extract = AsyncMock(return_value={"vector": [0.2] * 512, "description": {}})

    await gen.generate_and_store_plate(
        project_id="p1", kind="character", key="Mia:uniform",
        prompt="same person, navy uniform", base_image_url="https://oss/face.png")
    # a face reference routes through the image-edit path, not text-to-image
    gen.qwen.edit_image.assert_awaited_once()
    assert gen.qwen.edit_image.call_args.args[1] == "https://oss/face.png"
    gen.qwen.generate_image.assert_not_called()
    assert gen.last_face_preserved is True  # the shipped face IS the reference


@pytest.mark.asyncio
async def test_character_plate_reuses_reference_when_edit_refused():
    # When the edit model refuses the reference (e.g. DataInspectionFailed), do NOT
    # spend on a text-to-image fallback that ships a stranger's face — reuse the
    # already-valid reference plate instead so the user isn't billed for junk.
    gen = PlateGenerator.__new__(PlateGenerator)
    gen.qwen = MagicMock()
    gen.qwen.edit_image = AsyncMock(side_effect=RuntimeError("edit model 400"))
    gen.qwen.generate_image = AsyncMock(return_value="https://img/text.png")
    gen.oss = MagicMock()
    gen.oss.get_project_path = MagicMock(return_value="proj/plates/x.png")
    gen.oss.upload_bytes = MagicMock(return_value="https://oss/x.png")
    gen._fetch_bytes = MagicMock(return_value=b"imgbytes")
    gen.embedder = MagicMock()
    gen.embedder.extract = AsyncMock(return_value={"vector": [0.3] * 512, "description": {}})

    url, _ = await gen.generate_and_store_plate(
        project_id="p1", kind="character", key="Mia:uniform",
        prompt="same person, navy uniform", base_image_url="https://oss/face.png")
    assert url == "https://oss/face.png"          # reused the reference plate
    gen.qwen.generate_image.assert_not_awaited()  # NO wasted text-to-image render
    # the edit was refused, so callers badge the plate ref_rejected
    assert gen.last_face_preserved is False


@pytest.mark.asyncio
async def test_identity_mismatch_rerolls_and_keeps_the_closest_face():
    # attempt 1 renders a stranger (cosine 0.1 vs the reference); the plate is
    # re-rolled once and the better attempt (0.6) ships. One extra image, no
    # stranger in the character's costume.
    gen = PlateGenerator.__new__(PlateGenerator)
    gen.db = None
    gen.qwen = MagicMock()
    gen.qwen.edit_image = AsyncMock(side_effect=["https://img/a.png", "https://img/b.png"])
    gen.qwen.generate_image = AsyncMock()
    gen.oss = MagicMock()
    gen.oss.get_project_path = MagicMock(return_value="proj/plates/x.png")
    gen.oss.upload_bytes = MagicMock(return_value="https://oss/x.png")
    gen._fetch_bytes = MagicMock(side_effect=[b"stranger", b"match"])
    ref = [1.0] + [0.0] * 511
    stranger = [0.1] + [(1 - 0.1**2) ** 0.5] + [0.0] * 510   # cosine 0.1
    match = [0.6] + [(1 - 0.6**2) ** 0.5] + [0.0] * 510      # cosine 0.6
    gen.embedder = MagicMock()
    gen.embedder.model = MagicMock()
    gen.embedder.model.embed = MagicMock(side_effect=[stranger, match])
    gen.embedder.extract = AsyncMock(return_value={"vector": match, "description": {}})

    url, _ = await gen.generate_and_store_plate(
        project_id="p1", kind="character", key="Mia:uniform",
        prompt="same person, navy uniform",
        base_image_url="https://oss/face.png", match_vector=ref)
    assert gen.qwen.edit_image.await_count == 2       # re-rolled once
    assert gen.oss.upload_bytes.call_args.args[0] == b"match"  # best attempt ships
    assert url == "https://oss/x.png"


@pytest.mark.asyncio
async def test_identity_match_on_first_try_needs_no_retry():
    gen = PlateGenerator.__new__(PlateGenerator)
    gen.db = None
    gen.qwen = MagicMock()
    gen.qwen.edit_image = AsyncMock(return_value="https://img/a.png")
    gen.qwen.generate_image = AsyncMock()
    gen.oss = MagicMock()
    gen.oss.get_project_path = MagicMock(return_value="proj/plates/x.png")
    gen.oss.upload_bytes = MagicMock(return_value="https://oss/x.png")
    gen._fetch_bytes = MagicMock(return_value=b"good")
    ref = [1.0] + [0.0] * 511
    close = [0.5] + [(1 - 0.5**2) ** 0.5] + [0.0] * 510      # cosine 0.5 >= 0.35
    gen.embedder = MagicMock()
    gen.embedder.model = MagicMock()
    gen.embedder.model.embed = MagicMock(return_value=close)
    gen.embedder.extract = AsyncMock(return_value={"vector": close, "description": {}})

    await gen.generate_and_store_plate(
        project_id="p1", kind="character", key="Mia:uniform",
        prompt="same person, navy uniform",
        base_image_url="https://oss/face.png", match_vector=ref)
    gen.qwen.edit_image.assert_awaited_once()  # no wasted second image


@pytest.mark.asyncio
async def test_match_vector_from_pgvector_is_a_numpy_array():
    # face_vector loads from the DB as a numpy array — bool(array) raises
    # ("truth value of an array is ambiguous") and killed every verified plate
    import numpy as np
    gen = PlateGenerator.__new__(PlateGenerator)
    gen.db = None
    gen.qwen = MagicMock()
    gen.qwen.edit_image = AsyncMock(return_value="https://img/a.png")
    gen.qwen.generate_image = AsyncMock()
    gen.oss = MagicMock()
    gen.oss.get_project_path = MagicMock(return_value="proj/plates/x.png")
    gen.oss.upload_bytes = MagicMock(return_value="https://oss/x.png")
    gen._fetch_bytes = MagicMock(return_value=b"good")
    ref = np.array([1.0] + [0.0] * 511)
    close = [0.5] + [(1 - 0.5**2) ** 0.5] + [0.0] * 510
    gen.embedder = MagicMock()
    gen.embedder.model = MagicMock()
    gen.embedder.model.embed = MagicMock(return_value=close)
    gen.embedder.extract = AsyncMock(return_value={"vector": close, "description": {}})

    url, _ = await gen.generate_and_store_plate(
        project_id="p1", kind="character", key="Mia:uniform",
        prompt="same person, navy uniform",
        base_image_url="https://oss/face.png", match_vector=ref)
    assert url == "https://oss/x.png"
    gen.qwen.edit_image.assert_awaited_once()


def test_costume_plate_is_full_body_standing():
    # the plate standard: a fixed standing pose, face clearly visible, the
    # whole costume readable down to the shoes — never a scene performance
    from app.services.plate_generator import character_plate_prompt
    p = character_plate_prompt(True, "a woman around 20s", "navy sweater, jeans")
    assert "standing" in p
    assert "head to shoes" in p
    assert "waist-up" not in p


def test_outfit_scene_fluff_is_cleaned_from_the_plate():
    # the wardrobe text leaked scene context ("sitting by the window, staring
    # at the sea") and the model rendered the pose into the costume plate
    from app.services.plate_generator import character_plate_prompt
    p = character_plate_prompt(
        True, "a woman",
        "navy sweater and slim trousers, sitting by the window, staring at the sea")
    # the outfit clause of the prompt carries only wardrobe (the frame text
    # legitimately says 'Never sitting...' as an instruction)
    wearing = p.split("Wearing ", 1)[1].split(". Render")[0]
    assert "navy sweater" in wearing
    assert "sitting" not in wearing
    assert "window" not in wearing
    assert "sea" not in wearing


def test_negative_bans_sitting_not_full_body():
    from app.services.plate_generator import CHAR_PLATE_NEGATIVE
    assert "sitting" in CHAR_PLATE_NEGATIVE
    assert "full body" not in CHAR_PLATE_NEGATIVE


def test_eyewear_banned_unless_the_character_asks_for_it():
    from app.services.plate_generator import char_plate_negative, CHAR_PLATE_NEGATIVE
    # invented glasses were getting locked into seeded identities — ban by default
    assert "eyeglasses" in char_plate_negative("gentle gaze, refined jawline", "", None)
    # a character whose own description wears glasses keeps them
    assert char_plate_negative("always wears round glasses", "") == CHAR_PLATE_NEGATIVE
    # outfit-level eyewear (e.g. sunglasses from an outfit swap) also lifts the ban
    assert char_plate_negative("", "", "black suit with aviator sunglasses") == CHAR_PLATE_NEGATIVE


@pytest.mark.asyncio
async def test_face_reference_preflight_classifies_verdicts():
    """The upload-time probe: DataInspectionFailed (public figure) reads as
    rejected, a successful edit as ok, and any other failure as unknown so a
    flaky probe never blocks an upload."""
    from app.services.qwen_client import QwenClient
    client = QwenClient.__new__(QwenClient)

    client.edit_image = AsyncMock(side_effect=RuntimeError(
        'DashScope image-edit 400: {"code":"DataInspectionFailed"}'))
    assert await client.check_face_reference("https://oss/haaland.jpg") == "rejected"

    client.edit_image = AsyncMock(return_value="https://img/probe.png")
    assert await client.check_face_reference("https://oss/me.jpg") == "ok"

    client.edit_image = AsyncMock(side_effect=RuntimeError("timeout"))
    assert await client.check_face_reference("https://oss/me.jpg") == "unknown"


def test_creature_plate_prompt_drops_the_human_pose_standard():
    # a rabbit cannot stand straight with arms at its sides — the creature
    # plate asks for a natural full-body reference instead
    from app.services.plate_generator import character_plate_prompt
    p = character_plate_prompt(False, "a small white rabbit, red collar",
                               creature=True)
    assert "head to shoes" not in p
    assert "arms relaxed" not in p
    assert "Never sitting" not in p
    assert "full body" in p.lower()
    assert "ONE creature" in p
    # identity discipline survives: plain backdrop, no scene
    assert "plain seamless neutral backdrop" in p


def test_creature_negative_keeps_identity_bans_but_allows_natural_poses():
    from app.services.plate_generator import char_plate_negative
    n = char_plate_negative("a small white rabbit", creature=True)
    assert "two people" in n            # never a second subject
    assert "text, watermark" in n
    assert "sitting" not in n           # animals sit naturally
    assert "human, person" in n         # and never a person instead


def test_negated_eyewear_still_bans_glasses_on_the_plate():
    # the fragment said no glasses, the naive substring match read glasses
    # and skipped the ban — so the PLATE invented specs while every render
    # (correctly) obeyed the text, and they disagreed forever
    from app.services.plate_generator import char_plate_negative, wears_eyewear
    assert wears_eyewear("thin black rectangular glasses") is True
    assert wears_eyewear("clean-shaven face, no glasses") is False
    assert wears_eyewear("without glasses, short hair") is False
    n = char_plate_negative("an 8-year-old girl, no glasses")
    assert "eyeglasses" in n
    n2 = char_plate_negative("a man with thin black glasses")
    assert "eyeglasses" not in n2


def test_plate_prompt_strips_inherited_glasses():
    # a bespectacled LOCKED face beats the negative ban: the edit keeps the
    # face it sees, specs included — a non-wearer needs the removal said
    # positively in the prompt
    from app.services.plate_generator import character_plate_prompt
    p = character_plate_prompt(True, "a 17-year-old boy", "denim jacket",
                               strip_eyewear=True)
    assert "Remove any eyeglasses" in p
    p2 = character_plate_prompt(True, "a 17-year-old boy", "denim jacket")
    assert "Remove any eyeglasses" not in p2


def test_subject_descriptor_children_lead_as_kids_not_adults():
    # the Angeline plate prompt opened "a woman around 8" — the gendered lead
    # ignored age, gambling that the age number wins over "woman". A minor's
    # lead must SAY child ("a girl / a boy"), or the plate can render an adult.
    from app.services.plate_generator import subject_descriptor
    assert subject_descriptor("female", "8", "freckles").startswith("a girl around 8")
    assert subject_descriptor("male", "12", "wiry build").startswith("a boy around 12")
    # adults keep the existing leads
    assert subject_descriptor("female", "30s", "sharp suit").startswith("a woman around 30s")
    assert subject_descriptor("male", "45", "grey beard").startswith("a man around 45")
    # a written-out age counts too
    assert subject_descriptor("female", "8-year-old", "x").startswith("a girl around 8")


def test_character_plate_prompt_carries_the_visual_style():
    # the style picker's look must reach the COSTUME plates: without a style
    # clause the plates render photoreal and fight the style frame at video
    # time (a pixar drama with photographic cast references)
    from app.services.plate_generator import character_plate_prompt
    seed = "pixar style 3d animated feature look, soft global illumination"
    p = character_plate_prompt(False, "a girl around 8", "yellow raincoat",
                               style=seed)
    assert seed in p
    assert "never photorealistic" in p


def test_character_plate_prompt_styled_edit_keeps_the_likeness():
    # uploaded-face path: the edit must RESTYLE the person, not replace them.
    # PROVEN LIVE: a style clause APPENDED to the photo-preserving prompt is
    # ignored (the plate stays a photograph); the edit model only restyles
    # when the prompt LEADS with the repaint instruction.
    from app.services.plate_generator import character_plate_prompt
    seed = "watercolor painting style, soft bleeding washes"
    p = character_plate_prompt(True, "a woman around 20s", "navy sweater",
                               style=seed)
    assert p.startswith(f"Repaint this entire image as {seed}")
    assert "NOT look like a photograph" in p
    assert "recognizable" in p
    assert "navy sweater" in p
    assert "head to shoes" in p


def test_character_plate_prompt_without_style_is_unchanged():
    # photoreal dramas keep today's exact prompt — no stray style clause
    from app.services.plate_generator import character_plate_prompt
    p_default = character_plate_prompt(True, "a woman around 20s", "navy sweater")
    p_empty = character_plate_prompt(True, "a woman around 20s", "navy sweater",
                                     style="")
    assert p_default == p_empty
    assert "art style" not in p_default


def test_creature_plate_prompt_carries_the_visual_style_too():
    from app.services.plate_generator import character_plate_prompt
    seed = "claymation style, sculpted clay characters"
    p = character_plate_prompt(False, "a small white rabbit", "",
                               creature=True, style=seed)
    assert seed in p


def test_clean_appearance_drops_emotional_states():
    # "visibly distressed and tearful" survived (regex knew tears, not
    # tearful) and the ghibli repaint painted a crying reference plate
    from app.services.plate_generator import clean_appearance
    out = clean_appearance(
        "An 8-year-old girl with red eyes from crying, visibly distressed "
        "and tearful, long dark hair")
    assert "tearful" not in out
    assert "distressed" not in out
    assert "long dark hair" in out


def test_styled_edit_keeps_plate_backdrop_plain():
    # the ghibli seed says "lush natural backgrounds" — correct for shots,
    # wrong for a reference plate; the repaint lead must filter background
    # words from the seed and pin the studio backdrop
    from app.services.plate_generator import character_plate_prompt
    seed = "ghibli inspired hand-painted animation style, lush natural backgrounds, soft warm light"
    p = character_plate_prompt(True, "a girl around 8", "blue denim dress",
                               style=seed)
    assert "natural backgrounds" not in p
    assert "hand-painted animation style" in p
    assert "do not paint scenery" in p


def test_wears_eyewear_reads_chinese():
    from app.services.plate_generator import wears_eyewear
    assert wears_eyewear("一位戴着眼镜的中年教师") is True
    assert wears_eyewear("一位不戴眼镜的年轻人") is False
    assert wears_eyewear("十岁女孩，红色发箍") is False
