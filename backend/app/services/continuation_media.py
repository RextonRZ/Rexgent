"""Pure builders for the DashScope video `media[]` payloads, one place for the
confirmed request-shape rules so a wrong shape can't leak into dispatch:

- wan2.7-i2v accepts first_frame / last_frame / first_clip ONLY.
- wan2.7-r2v accepts up to 5 reference_image entries PLUS an optional first_frame
  together (joint control: continue the scene AND lock the references).
"""


def hold_media(*, first_clip_url=None, first_frame_url=None,
               want_seconds=None, first_clip_seconds=None):
    """Continue-Hold media for wan2.7-i2v.

    Silent continuation: first_clip if available (best motion), else
    first_frame. Returns None when there is nothing to continue from.

    first_clip carries a DashScope hard constraint: the REQUESTED duration
    must exceed the seed clip's length or the task fails server-side
    ('first_clip duration must be less than the requested duration') — a 3s
    beat can never continue a 5s clip. When durations are supplied, first_clip
    is used only when want_seconds > first_clip_seconds; a known-short request
    with an unknown seed length falls back to first_frame (which has no
    duration constraint). Legacy calls without durations keep old behavior."""
    if first_clip_url:
        if want_seconds is None:
            return [{"type": "first_clip", "url": first_clip_url}]
        if first_clip_seconds is not None and want_seconds > first_clip_seconds:
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
