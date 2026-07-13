"""Identity-role classification for a shot — a pure function that decides which
video model a shot should render on, so face/costume are locked or continued by
the model whose real strength fits. No I/O; the caller supplies the booleans.

Roles:
  anchor           - establishing / no previous frame to continue -> r2v + full plate stack
  entrance         - a new face-locked character enters -> r2v with first_frame + newcomer refs
  continue_reangle - deliberate camera-angle change within the beat -> r2v with first_frame + refs
  continue_hold    - same people/outfit/angle -> wan i2v continuation from the previous clip/frame
"""


def classify_shot_role(*, has_frame_anchor: bool, has_locked_newcomer: bool,
                       angle_changed: bool) -> str:
    if not has_frame_anchor:
        return "anchor"
    if has_locked_newcomer:
        return "entrance"
    if angle_changed:
        return "continue_reangle"
    return "continue_hold"


def angle_changed(prev_shot_type, cur_shot_type, reverse_angle: bool) -> bool:
    """True when this shot is a deliberate camera move vs the previous shot: an
    explicit reverse-angle flag, or a different shot_type (framing). A pure Wan
    continuation copies the previous frame, so a genuine angle change must NOT be
    left to it — this signal routes those shots to r2v instead."""
    if reverse_angle:
        return True
    return _norm(prev_shot_type) != _norm(cur_shot_type)


def _norm(shot_type) -> str:
    return str(shot_type or "").strip().upper()
