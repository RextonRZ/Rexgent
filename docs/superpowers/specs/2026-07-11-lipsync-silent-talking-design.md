# Silent Talking + Wan Lip-Sync — Design

**Date:** 2026-07-11
**Status:** Approved (brainstormed with owner)

## Problem

Video models hallucinate their own speech audio (often Chinese/Korean chatter) and
render talking behavior inconsistently: some dialogue shots show closed mouths,
some show random people talking. The real dialogue is TTS, synthesized before
rendering and overlaid at export, where speaking shots' fake audio is already
muted. Two gaps remain:

1. The **picture** does not reliably show the speaker talking.
2. Lips never match the spoken words — a visible seam judges will notice.

## Goals

- Every dialogue shot *looks* like the speaker is talking (Stage 1, zero render cost).
- Eligible shots get true lip-sync: the mouth is driven by the shot's actual TTS
  line via wan2.7 `driving_audio` (Stage 2, no extra per-shot cost vs a normal wan render).
- Demo-safe: any lip-sync failure falls back to today's pipeline automatically;
  a one-line kill switch disables it entirely.

## Non-Goals

- Lip-sync on happyhorse-tier shots (the model has no audio-driven mode).
- Lip-sync for shots speaking multiple (folded) lines or multi-speaker framings.
- Changing export placement, mixing, or captions in any way.

## Stage 1 — Silent talking (prompt polish)

`ScenePromptCraft.craft` gains a dialogue block, built the same way as the
existing setting/continuity/foreground blocks: when the shot has dialogue, the
prompt instructs that the speaking character is visibly mid-conversation —
natural mouth movement, conversational gesture and eye focus — while the
existing sanitizer keeps text/subtitles out of frame. Non-speaking shots are
unchanged. No API or cost impact; audio remains export's job.

## Stage 2 — Wan lip-sync

### Eligibility (ALL must hold)

1. Shot is wan tier.
2. A frame anchor exists (previous shot's last frame, or the scene anchor) —
   wan i2v requires `first_frame`.
3. The shot speaks **exactly one** line: its speaking-index within the scene
   (position among non-deferred dialogue-bearing shots, ordered by shot number —
   the same k-th-line/k-th-speaking-shot convention `place_dialogue` uses) maps
   to exactly one `LineAudio` row, and the scene has no folded overflow landing
   on this shot.
4. Exactly one non-foreground character is in frame, and it matches the line's
   `character_name` (canonical, case-insensitive).
5. `settings.lipsync_enabled` is true (env `LIPSYNC_ENABLED`, default true).

### Data flow

- The line's `audio_url` is already OSS-hosted and public (a wan requirement)
  because voice synthesis runs before rendering (audio-first).
- The wan call becomes:
  `reference_media=[{"type": "first_frame", "url": anchor}, {"type": "driving_audio", "url": line.audio_url}]`
  with prompt, seed, ratio and the fitted duration unchanged. The duration
  fitter already guarantees the shot is long enough to hold the line.
- `used_tier` stays `wan`; clip row and cost ledger unchanged in shape.

### Export interplay (unchanged by design)

The lip-synced clip's baked audio is still muted at stitch (existing speaking-shot
mute policy) and the same TTS line still overlays at the shot's start. Because
the mouth was driven by that identical audio and the line anchors at the shot
start, lips and voice align within ~0.1s, and voice quality stays uniform with
non-lip-synced shots.

## Failure handling

Fallback chain inside the existing retry loop, never blocking a shot:

1. wan `first_frame + driving_audio` fails → retry the attempt as plain wan
   `first_frame` (today's path).
2. That fails → happyhorse r2v with the bible stack (today's fallback),
   `used_tier` recorded as happyhorse.
3. Kill switch: `LIPSYNC_ENABLED=false` skips eligibility entirely.

A lip-sync attempt that renders but *looks* wrong is handled by the existing
continuity scoring + Edit-room review, like any other take.

## Testing

- Unit: eligibility resolver (folded lines, multi-speaker, foreground-occluded,
  missing anchor, flag off) and the wan payload shape.
- Live validation (~$2, already owed): the current drama's two dead wan shots
  re-render via the resume-skip run. Scene 1 shot 4 is wan, single-line,
  frame-anchored → it validates lip-sync end to end. Acceptance: renders
  successfully, mouth movement visibly tracks the line, export plays in sync.
- If the live result looks bad: leave the code, set `LIPSYNC_ENABLED=false`.

## Risks

- Wan may reject the `first_frame + driving_audio` combination on some accounts
  or durations — covered by the fallback chain (worst case: today's behavior).
- Driven mouth quality is unknown until the test render — covered by the kill
  switch and per-take Edit-room review.
- Folded-line scenes get no lip-sync by design; Stage 1 keeps them looking natural.
