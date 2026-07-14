from dataclasses import dataclass, field


@dataclass
class PlannedShot:
    purpose: str            # establishing|dialogue|reaction|insert|reveal|beat|climax|transition|resolution
    shot_size: str          # ECU|CU|MCU|MS|FS|LS|EWS|OTS|POV|INSERT
    camera_movement: str    # STATIC|PAN_LEFT|PAN_RIGHT|TILT_UP|TILT_DOWN|DOLLY_IN|DOLLY_OUT|HANDHELD|DRONE
    lens: str               # 24mm|35mm|50mm|85mm|135mm
    composition: str
    intended_duration: float
    covers_lines: list[int]        # dialogue-line indices this shot carries; empty for a silent beat
    action_beat: str               # the physical/visual beat shown; never just "speaks"
    blocking_delta: str | None = None
    transition_in: str | None = None


@dataclass
class ShotPlan:
    shots: list[PlannedShot] = field(default_factory=list)


@dataclass
class LookProfile:
    lighting: str
    colour_mood: str
    lens_bias: str
    camera_pace: str        # "slow" | "measured" | "kinetic"
    bgm_hint: str | None = None
    ambience_hint: str | None = None
