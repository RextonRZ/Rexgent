"""Pure builders for the DashScope video `media[]` payloads, one place for the
confirmed request-shape rules so a wrong shape can't leak into dispatch:

- wan2.7-i2v accepts first_frame / last_frame / first_clip / driving_audio ONLY.
  driving_audio is valid ONLY alongside first_frame (never first_clip).
- wan2.7-r2v accepts up to 5 reference_image entries PLUS an optional first_frame
  together (joint control: continue the scene AND lock the references).
"""


def hold_media(*, first_clip_url=None, first_frame_url=None, audio_url=None,
               talking: bool = False):
    """Continue-Hold media for wan2.7-i2v.

    Talking + both frame and audio present -> first_frame + driving_audio (lip-sync).
    Otherwise silent continuation: first_clip if available (best motion), else
    first_frame. Returns None when there is nothing to continue from."""
    if talking and first_frame_url and audio_url:
        return [{"type": "first_frame", "url": first_frame_url},
                {"type": "driving_audio", "url": audio_url}]
    if first_clip_url:
        return [{"type": "first_clip", "url": first_clip_url}]
    if first_frame_url:
        return [{"type": "first_frame", "url": first_frame_url}]
    return None


def r2v_media(ref_stack, *, first_frame_url=None):
    """wan2.7-r2v media: the reference_image plate stack, optionally led by a
    first_frame for joint control (Entrance / Reangle continue the scene while
    the plates lock identity+costume). r2v is defined by its references, so this
    returns None when there are no reference images left (a lone first_frame is
    an i2v continuation, not an r2v job). If the first_frame URL already appears
    in the stack (the prev_frame reference), it is not sent twice."""
    stack = [e for e in (ref_stack or []) if e.get("url") != first_frame_url]
    if not stack:
        return None
    if first_frame_url:
        return [{"type": "first_frame", "url": first_frame_url}] + stack
    return stack
