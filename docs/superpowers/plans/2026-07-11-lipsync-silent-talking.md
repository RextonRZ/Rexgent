# Silent Talking + Wan Lip-Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dialogue shots visibly show the speaker talking (prompt polish), and narrowly-eligible wan shots get true lip-sync by driving the mouth with the shot's own TTS line, with an automatic fallback chain and a kill switch.

**Architecture:** Stage 1 adds a dialogue-delivery block to the scene prompt crafter (pure prompt change). Stage 2 adds a small pure module (`app/services/lipsync.py`) that resolves which single line a shot speaks and whether the visible speaker matches, and the generation runner uses it to render eligible wan shots with `first_frame + driving_audio`; any failure falls back to plain wan first-frame, then happyhorse r2v. Export is untouched (fake audio on speaking shots is already muted; TTS overlays as today).

**Tech Stack:** FastAPI backend, SQLAlchemy, pydantic-settings, DashScope wan2.7-i2v (`reference_media` types: `first_frame`, `driving_audio`), pytest.

**Spec:** `docs/superpowers/specs/2026-07-11-lipsync-silent-talking-design.md`

---

### Task 1: Kill switch setting

**Files:**
- Modify: `backend/app/config.py` (Settings class, after `qwen_vl_continuity_model`)

- [ ] **Step 1: Add the setting**

In `backend/app/config.py`, find:

```python
    qwen_vl_continuity_model: str = "qwen3-vl-plus"
```

Add directly below it:

```python
    # Wan lip-sync (first_frame + driving_audio on eligible shots). Flip to
    # false to disable instantly — the fallback path is today's renderer.
    lipsync_enabled: bool = True
```

pydantic-settings maps this to env var `LIPSYNC_ENABLED` automatically.

- [ ] **Step 2: Verify nothing broke**

Run: `cd backend && python -m pytest -q`
Expected: all tests pass (398 at time of writing).

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat(lipsync): kill switch setting, LIPSYNC_ENABLED defaults on"
```

---

### Task 2: Pure eligibility module

**Files:**
- Create: `backend/app/services/lipsync.py`
- Test: `backend/tests/test_lipsync.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_lipsync.py`:

```python
from app.services.lipsync import pick_lipsync_line, speaker_matches, lipsync_media


LINES = [
    {"audio_url": "https://oss/l0.wav", "character_name": "IM SOL"},
    {"audio_url": "https://oss/l1.wav", "character_name": "RYU SUN-JAE"},
]


def test_kth_speaking_shot_gets_kth_line():
    # the same convention place_dialogue uses: k-th line -> k-th speaking shot
    assert pick_lipsync_line("s2", ["s1", "s2"], LINES) == LINES[1]


def test_non_speaking_shot_gets_nothing():
    assert pick_lipsync_line("sX", ["s1", "s2"], LINES) is None


def test_shot_beyond_the_lines_gets_nothing():
    assert pick_lipsync_line("s2", ["s1", "s2"], LINES[:1]) is None


def test_folded_overflow_shot_is_ineligible():
    # 3 lines, 2 speaking shots: the LAST speaking shot carries lines 1 AND 2
    # at placement — a mouth can't be driven by two lines, so no lip-sync
    three = LINES + [{"audio_url": "https://oss/l2.wav", "character_name": "IM SOL"}]
    assert pick_lipsync_line("s2", ["s1", "s2"], three) is None
    # the first shot still speaks exactly one line
    assert pick_lipsync_line("s1", ["s1", "s2"], three) == three[0]


def test_speaker_must_be_the_only_visible_character():
    line = {"character_name": "IM SOL"}
    assert speaker_matches(line, ["IM SOL"], []) is True
    # case-insensitive
    assert speaker_matches({"character_name": "im sol"}, ["IM SOL"], []) is True
    # two visible people -> no
    assert speaker_matches(line, ["IM SOL", "RYU SUN-JAE"], []) is False
    # the other person is a foreground occluder (face unseen) -> yes
    assert speaker_matches(line, ["IM SOL", "RYU SUN-JAE"], ["RYU SUN-JAE"]) is True
    # the visible person is NOT the speaker -> no
    assert speaker_matches(line, ["RYU SUN-JAE"], []) is False
    # nobody visible -> no
    assert speaker_matches(line, ["RYU SUN-JAE"], ["RYU SUN-JAE"]) is False


def test_lipsync_media_shape():
    media = lipsync_media("https://oss/frame.jpg", "https://oss/l0.wav")
    assert media == [
        {"type": "first_frame", "url": "https://oss/frame.jpg"},
        {"type": "driving_audio", "url": "https://oss/l0.wav"},
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_lipsync.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.lipsync'`

- [ ] **Step 3: Write the implementation**

Create `backend/app/services/lipsync.py`:

```python
"""Wan lip-sync eligibility — pure functions, no I/O.

A shot may be lip-synced (wan `first_frame + driving_audio`) only when it
speaks EXACTLY one line and the speaker is the only visible face. The line
mapping follows the same convention `place_dialogue` uses: the k-th dialogue
line of a scene belongs to the scene's k-th speaking shot, and overflow lines
fold onto the LAST speaking shot — which therefore never lip-syncs.
"""


def pick_lipsync_line(shot_id, speaking_shot_ids: list, lines: list[dict]) -> dict | None:
    """The single line this shot speaks, or None when it has none / has many."""
    if shot_id not in speaking_shot_ids:
        return None
    idx = speaking_shot_ids.index(shot_id)
    if idx >= len(lines):
        return None
    is_last = idx == len(speaking_shot_ids) - 1
    if is_last and len(lines) > len(speaking_shot_ids):
        return None  # folded overflow: this shot carries several lines
    return lines[idx]


def speaker_matches(line: dict, in_frame: list, foreground: list) -> bool:
    """True when the line's speaker is the ONLY non-occluded face in frame."""
    fg = {str(n).strip().upper() for n in (foreground or [])}
    visible = [str(n).strip().upper() for n in (in_frame or [])
               if str(n).strip().upper() not in fg]
    speaker = str(line.get("character_name") or "").strip().upper()
    return len(visible) == 1 and bool(speaker) and visible[0] == speaker


def lipsync_media(anchor_url: str, audio_url: str) -> list[dict]:
    """The wan2.7-i2v media payload: continue from the frame, drive the mouth."""
    return [
        {"type": "first_frame", "url": anchor_url},
        {"type": "driving_audio", "url": audio_url},
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_lipsync.py -q`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/lipsync.py backend/tests/test_lipsync.py
git commit -m "feat(lipsync): pure eligibility — one line, one visible speaker, media payload"
```

---

### Task 3: Stage 1 — silent talking prompt block

**Files:**
- Modify: `backend/app/mcp_tools/scene_prompt_craft.py` (inside `craft`, after `foreground_block`)
- Test: `backend/tests/test_scene_prompt_craft.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_scene_prompt_craft.py`:

```python
@pytest.mark.asyncio
async def test_dialogue_shot_gets_delivery_block():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "x", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"

    await crafter.craft(
        shot={"shot_type": "MCU", "dialogue": "We need to go, now."},
        character_visuals={}, target_model="happyhorse")
    user_msg = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "Dialogue delivery" in user_msg
    assert "mid-conversation" in user_msg


@pytest.mark.asyncio
async def test_silent_shot_has_no_delivery_block():
    crafter = ScenePromptCraft.__new__(ScenePromptCraft)
    crafter.qwen = MagicMock()
    crafter.qwen.chat_json = AsyncMock(return_value={
        "prompt": "x", "negative_prompt": "", "model_parameters": {}})
    crafter.prompt_template = "placeholder"

    await crafter.craft(shot={"shot_type": "WS"}, character_visuals={},
                        target_model="happyhorse")
    user_msg = crafter.qwen.chat_json.await_args.kwargs["messages"][1]["content"]
    assert "Dialogue delivery" not in user_msg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_scene_prompt_craft.py -q`
Expected: the two new tests FAIL (`"Dialogue delivery" in user_msg` assertion error); older ones pass.

- [ ] **Step 3: Add the block in `craft`**

In `backend/app/mcp_tools/scene_prompt_craft.py`, find:

```python
        foreground_block = (
            f"Foreground occlusion (rule 15 — show ONLY as a soft-focus back or "
            f"shoulder in the near foreground, face turned away and not visible; "
            f"do NOT make them a co-subject): {json.dumps(list(foreground_characters), ensure_ascii=False)}\n\n"
            if foreground_characters else ""
        )
```

Add directly below it:

```python
        # Dialogue shots must LOOK like talking: the model otherwise renders
        # closed mouths or random extras chattering. Audio stays export's job
        # (TTS overlays there); this rule shapes only the picture.
        dialogue_block = (
            "Dialogue delivery (rule 16 — the speaker is visibly mid-conversation: "
            "natural mouth movement while speaking, conversational gesture, eye "
            "focus on the listener or camera; NO on-screen text or subtitles): "
            f"{json.dumps(str(shot.get('dialogue'))[:160], ensure_ascii=False)}\n\n"
            if str(shot.get("dialogue") or "").strip() else ""
        )
```

Then find:

```python
            f"{foreground_block}"
```

and change it to:

```python
            f"{foreground_block}"
            f"{dialogue_block}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_scene_prompt_craft.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/mcp_tools/scene_prompt_craft.py backend/tests/test_scene_prompt_craft.py
git commit -m "feat(prompt): dialogue shots render the speaker visibly mid-conversation"
```

---

### Task 4: Runner wiring — driving_audio with the fallback chain

**Files:**
- Modify: `backend/app/services/generation_runner.py` (two places: `_run_scene` and `_process_shot`)

- [ ] **Step 1: Resolve each scene's lines once, pass the shot's line down**

In `_run_scene`, find:

```python
            already_good = getattr(self, "_approved_shot_ids", set())
            active = [s for s in shots
                      if (s.quality_tier or "") != "deferred"
                      and s.id not in already_good]
```

Add directly below it:

```python
            # lip-sync inputs: the scene's synthesized lines (audio-first, so
            # they exist before rendering) + which shots speak, in order. The
            # k-th speaking shot speaks the k-th line — same convention as
            # place_dialogue, so mouth and overlay can't disagree.
            from app.services.lipsync import pick_lipsync_line
            from app.models.line_audio import LineAudio
            # over ALL non-deferred shots of the scene, NOT `active`: on a
            # resume run `active` excludes already-approved shots, which would
            # shift every speaking index and drive mouths with the WRONG line
            speaking_ids = [s.id for s in shots
                            if (s.quality_tier or "") != "deferred"
                            and (s.dialogue or "").strip()]
            line_rows = (db2.query(LineAudio)
                         .filter(LineAudio.project_id == job2.project_id,
                                 LineAudio.scene_number == scene.number)
                         .order_by(LineAudio.line_index).all())
            scene_lines = [{"audio_url": r.audio_url,
                            "character_name": r.character_name}
                           for r in line_rows if r.audio_url]
```

Then find the `_process_shot` call:

```python
                prev_last_frame = await r2._process_shot(
                    job2, shot, char_by_name, bible, scene.number, prev_last_frame,
                    scene_anchor_url=scene_anchor, scene_setting=scene_setting,
                    suppress_location=state_changed,
                    prev_action=prev_action, next_action=next_action)
```

and change it to:

```python
                prev_last_frame = await r2._process_shot(
                    job2, shot, char_by_name, bible, scene.number, prev_last_frame,
                    scene_anchor_url=scene_anchor, scene_setting=scene_setting,
                    suppress_location=state_changed,
                    prev_action=prev_action, next_action=next_action,
                    lipsync_line=pick_lipsync_line(shot.id, speaking_ids, scene_lines))
```

- [ ] **Step 2: Accept the line in `_process_shot`**

Find:

```python
    async def _process_shot(self, job, shot, char_by_name, bible, scene_number,
                            prev_last_frame_url, scene_anchor_url=None,
                            scene_setting=None, suppress_location=False,
                            prev_action=None, next_action=None):
```

and change it to:

```python
    async def _process_shot(self, job, shot, char_by_name, bible, scene_number,
                            prev_last_frame_url, scene_anchor_url=None,
                            scene_setting=None, suppress_location=False,
                            prev_action=None, next_action=None,
                            lipsync_line=None):
```

- [ ] **Step 3: Render eligible shots with driving audio, chain the fallbacks**

In `_process_shot`, find the current wan branch:

```python
                used_tier = shot.quality_tier or "happyhorse"
                if is_wan:
                    # wan2.7-i2v does NOT take identity references — its media
                    # schema is first_frame / last_frame / driving_audio /
                    # first_clip only (every reference_image call 400'd and the
                    # shot died). Give wan its REAL job: continue the scene
                    # from the previous shot's last frame. With no frame to
                    # continue from, the shot renders on HappyHorse r2v, which
                    # is the model that actually understands the bible stack.
                    frame_anchor = prev_last_frame_url or scene_anchor_url
                    if frame_anchor:
                        task_id = await self.qwen.generate_video_wan(
                            prompt=prompt, duration=shot.estimated_duration_seconds,
                            reference_media=[{"type": "first_frame", "url": frame_anchor}],
                            seed=seed, ratio=ratio)
                    else:
                        logger.info("shot %s: wan has no frame to continue from — "
                                    "rendering on happyhorse r2v with the bible stack",
                                    shot.id)
                        used_tier = "happyhorse"
                        task_id = await self.qwen.generate_video_happyhorse(
                            prompt=prompt, duration=shot.estimated_duration_seconds,
                            mode="r2v" if ref_stack else "t2v",
                            reference_media=ref_stack or None,
                            seed=seed, ratio=ratio)
```

Replace it with:

```python
                used_tier = shot.quality_tier or "happyhorse"
                if is_wan:
                    # wan2.7-i2v does NOT take identity references — its media
                    # schema is first_frame / last_frame / driving_audio /
                    # first_clip only. Give wan its REAL jobs: continue the
                    # scene from the previous shot's last frame, and when this
                    # shot speaks exactly one line with one visible speaker,
                    # DRIVE the mouth with that line's own TTS audio. Any
                    # failure falls down the chain: lip-sync -> plain
                    # first-frame -> happyhorse r2v. Never blocks the shot.
                    from app.config import get_settings as _settings
                    from app.services.lipsync import lipsync_media, speaker_matches
                    frame_anchor = prev_last_frame_url or scene_anchor_url
                    lip = (lipsync_line
                           if (_settings().lipsync_enabled
                               and frame_anchor
                               and lipsync_line
                               and lipsync_line.get("audio_url")
                               and speaker_matches(lipsync_line, in_frame, foreground))
                           else None)
                    task_id = None
                    if frame_anchor and lip:
                        try:
                            task_id = await self.qwen.generate_video_wan(
                                prompt=prompt, duration=shot.estimated_duration_seconds,
                                reference_media=lipsync_media(frame_anchor, lip["audio_url"]),
                                seed=seed, ratio=ratio)
                            logger.info("shot %s: lip-synced to its line", shot.id)
                        except Exception as le:  # noqa: BLE001 — never blocks
                            logger.warning("lip-sync dispatch failed for shot %s (%s) — "
                                           "falling back to plain first-frame", shot.id, le)
                    if task_id is None and frame_anchor:
                        try:
                            task_id = await self.qwen.generate_video_wan(
                                prompt=prompt, duration=shot.estimated_duration_seconds,
                                reference_media=[{"type": "first_frame", "url": frame_anchor}],
                                seed=seed, ratio=ratio)
                        except Exception as we:  # noqa: BLE001 — chain to happyhorse
                            logger.warning("wan first-frame failed for shot %s (%s) — "
                                           "falling back to happyhorse r2v", shot.id, we)
                    if task_id is None:
                        if not frame_anchor:
                            logger.info("shot %s: wan has no frame to continue from — "
                                        "rendering on happyhorse r2v with the bible stack",
                                        shot.id)
                        used_tier = "happyhorse"
                        task_id = await self.qwen.generate_video_happyhorse(
                            prompt=prompt, duration=shot.estimated_duration_seconds,
                            mode="r2v" if ref_stack else "t2v",
                            reference_media=ref_stack or None,
                            seed=seed, ratio=ratio)
```

- [ ] **Step 4: Run the full suite**

Run: `cd backend && python -m pytest -q`
Expected: all pass (407 after Tasks 2-3: 398 baseline + 7 lipsync + 2 crafter).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/generation_runner.py
git commit -m "feat(lipsync): eligible wan shots render with first_frame + driving_audio — the mouth moves to the shot's own TTS line, with fallback to plain first-frame then happyhorse and a LIPSYNC_ENABLED kill switch"
```

---

### Task 5: Live validation (manual, ~$2 already owed)

**Files:** none (operational)

- [ ] **Step 1: Restart the backend and Celery worker** so the new code is live.

- [ ] **Step 2: Re-run generation on the current drama** ("Lovely Runners"): Generate page → ▶ Start generation → confirm the spend modal. The resume-skip renders ONLY the two dead wan shots. Scene 1 shot 4 (wan, one line, frame-anchored, single speaker) is the lip-sync proof shot; scene 1 shot 2 has no frame anchor and will render on happyhorse — correct per eligibility.

- [ ] **Step 3: Check the backend log** for `shot <id>: lip-synced to its line` (proof the driving_audio path ran, not the fallback).

- [ ] **Step 4: Watch the take** on the Generate page (unmute the tile): mouth movement should visibly track the line's rhythm.

- [ ] **Step 5: Export and check sync** — the overlaid TTS line should sit on the moving mouth within ~0.1s.

- [ ] **Step 6: Verdict** — if it looks good, done. If it looks bad, set `LIPSYNC_ENABLED=false` in `backend/.env`, restart, and the demo runs exactly as today. Report the outcome either way.
