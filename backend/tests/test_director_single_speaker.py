"""A dialogue shot must voice ONE speaker. The Director could cover two
characters' lines in one shot; the Stager joined them into a speaker-less string
and the render made the wrong person say the other's line ("Deok-hyun speaks
Anna's 'Deok-hyun, what are you hiding?'"). Splitting fixes it at the source."""
from app.director.director import _enforce_single_speaker, apply_guardrails
from app.director.types import PlannedShot


def _mk(cov, purpose="dialogue"):
    return PlannedShot(purpose=purpose, shot_size="MS", camera_movement="STATIC",
                       lens="50mm", composition="rule_of_thirds", intended_duration=5.0,
                       covers_lines=list(cov), action_beat="talk")


def test_multi_speaker_shot_is_split_in_script_order():
    # the real bug: one shot covered ANNA(line1) + DEOK(line0), reversed order
    speakers = ["DEOK-HYUN", "ANNA"]  # line0=DEOK, line1=ANNA
    out = _enforce_single_speaker([_mk([1, 0])], speakers)
    assert len(out) == 2
    covs = [s.covers_lines for s in out]
    assert covs == [[0], [1]]                       # one speaker each, script order
    assert all(len(s.covers_lines) == 1 for s in out)


def test_same_speaker_lines_stay_one_shot():
    out = _enforce_single_speaker([_mk([0, 1])], ["ANNA", "ANNA"])
    assert len(out) == 1 and out[0].covers_lines == [0, 1]


def test_every_line_still_covered_exactly_once_through_guardrails():
    # 3 lines, alternating speakers, one greedy shot covering all
    speakers = ["DEOK-HYUN", "ANNA", "DEOK-HYUN"]
    plan = apply_guardrails([_mk([0, 1, 2])], n_lines=3, budget=6, line_speakers=speakers)
    covered = sorted(i for s in plan.shots for i in s.covers_lines)
    assert covered == [0, 1, 2]                     # no line dropped or duplicated
    # no shot mixes speakers
    for s in plan.shots:
        spk = {speakers[i] for i in s.covers_lines}
        assert len(spk) <= 1, s.covers_lines
