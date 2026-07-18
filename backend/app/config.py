from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    qwen_api_key: str = ""
    # Wan's reference-to-video snapshot: unlike wan2.7-t2v/i2v it accepts up
    # to 5 reference images, so premium shots that INTRODUCE a face-locked
    # character can stay premium instead of demoting to happyhorse
    qwen_wan_r2v_model: str = "wan2.7-r2v-2026-06-12"
    # Wan image-to-video snapshot. The DATED snapshot is what supports the
    # first_frame + driving_audio lip-sync feature; the bare "wan2.7-i2v" alias
    # resolves to an older i2v that IGNORES driving_audio, so a lip-sync shot
    # rendered on it comes back with a moving-but-unsynced mouth. Keep this
    # pinned to the snapshot the DashScope docs use for driving_audio.
    qwen_wan_i2v_model: str = "wan2.7-i2v-2026-04-25"
    qwen_wan_t2v_model: str = "wan2.7-t2v"
    # Identity-role routing (Anchor/Continue-Hold/Continue-Reangle/Entrance).
    # OFF by default: when false, generation_runner keeps today's exact routing.
    # Flip on per-deploy once the measurement harness (Phase 3) validates it.
    identity_routing_v2: bool = False
    # wan2.7-videoedit — used by the Phase 2 repair ladder (costume/face repair).
    # VERIFY-IN-CONSOLE: only the bare id was seen; a dated snapshot may exist.
    qwen_wan_videoedit_model: str = "wan2.7-videoedit"
    # Which reference model renders identity anchors/entrances/reangles under
    # identity_routing_v2. "happyhorse" (reference-native, measured to hold faces
    # better than wan r2v) is the SAFE DEFAULT; "wan" opts into wan2.7-r2v. Phase 3's
    # measurement harness sets this from real scores instead of a guess.
    anchor_ref_model: str = "happyhorse"
    # Verify-and-repair ladder: on a continuity fail, re-render/repair instead of
    # shipping the flagged clip. OFF by default. repair_max_renders bounds the
    # EXTRA renders per shot so cost can't explode.
    repair_enabled: bool = False
    repair_max_renders: int = 2
    # Multi-shot conversation beats: render a run of dialogue shots as ONE wan2.7
    # multi-shot clip (angles locked to the same faces), sliced back per shot at
    # export. OFF by default. max_shots bounds a beat; max_duration caps the merged
    # clip to wan's 2-15s range.
    multishot_enabled: bool = False
    multishot_max_shots: int = 3
    multishot_max_duration: int = 15
    happyhorse_native_talk: bool = False
    # Prepend an [Image N] legend to r2v prompts so the model ties each person to
    # their OWN reference plate (face/outfit) instead of guessing. OFF by default.
    image_ref_labels: bool = False
    # Render continuation (continue_hold) shots on HappyHorse r2v instead of Wan
    # i2v. Wan i2v continuation hard-fails when the previous clip is >= the
    # requested duration and can't lip-sync 2-face shots; HappyHorse r2v continues
    # via the reference stack (which already carries the prev frame) and does
    # multi-person native talk. ON by default; flip OFF for the old wan i2v path.
    route_continuation_to_happyhorse: bool = True
    # Wan-primary routing: HappyHorse renders talking shots + new/changed-face
    # shots; Wan renders every silent visual shot (continuation of established
    # faces, or scenery). Builds on identity_routing_v2. OFF -> today's routing.
    wan_primary: bool = False
    # Storyboard camera intent: when true, the storyboard prompt asks the model to
    # pick a PURPOSEFUL camera_movement per beat instead of defaulting to STATIC.
    # OFF by default — flag off leaves the storyboard prompt byte-identical to today.
    cinematic_prompt: bool = False
    # Two-pass Director->Stager shot planning (purpose/variety/pacing/action).
    # OFF by default: flag off leaves storyboard boarding byte-identical to today.
    director_engine: bool = False
    # Guarantee a Wan visual: when the first scene doesn't already open on a
    # people-free shot, prepend a short scenery establishing shot (empty cast,
    # no dialogue) that routes to Wan. OFF by default -> boarding unchanged.
    ensure_establishing_shot: bool = False
    # Weave silent Wan beats into every scene: held two-shots between dialogue
    # (same framing + cast, no line). OFF by default -> boarding unchanged.
    wan_beats: bool = False
    # Faceless atmosphere cutaways (people-free scenery mid-scene). Split from
    # wan_beats and OFF by default: in practice the empty-scenery inserts read
    # as disconnected from the drama, while the held beats (same cast, same
    # frame) are the Wan continuation that actually works.
    wan_atmosphere: bool = False
    # All-speech boarding: every shot carries a spoken line — silent beats
    # teleported postures between renders and read as filler. OFF -> unchanged.
    dialogue_only: bool = False
    # A scene that opens TIGHT (the hook) gets a brief silent wide right
    # after it: locks the room early so fresh r2v shots stop inventing their
    # own versions of the set. OFF -> boards unchanged.
    reorient_wide: bool = False
    # Held-frame breath (seconds) at every scene boundary in the export:
    # cuts stay tight within a scene, the scene CHANGE gets air. 0 -> off.
    scene_breath_seconds: float = 0.0
    # TTS voice overlay (restore in progress — see the 2026-07-16 plan): clips
    # keep rendering with native talk, but export mutes the clip audio and
    # lays per-line TTS (designed voices + instruct acting + mouth pacing).
    # Dormant until the plan's tasks 1-4 land; OFF -> native audio unchanged.
    tts_overlay: bool = False
    # Ground-truth frame handoff: a VL model reads the previous clip's ACTUAL
    # final frame (poses, props, door states) and the description feeds the
    # next shot's opening state — textual continuity that cannot duplicate
    # people the way a frame reference did. One VL call per shot.
    frame_handoff: bool = False
    # attach the previous shot's final frame as a reference image when provably
    # safe (same scene + non-shrinking cast) — the Blood and Bone continuity,
    # without the duplicate-people failure mode
    prev_frame_guarded: bool = False
    # trim every dialogue chunk at export to its measured speech span (+pads):
    # the fast cut-on-the-line rhythm of a vertical drama, instead of seconds
    # of silent holding after each line
    tight_cuts: bool = False
    # Continuity bridge: when the guarded prev-frame reference rides a shot,
    # the prompt orders the clip to OPEN on that exact frame, hold it a beat,
    # then move into the new staging as one continuous on-camera transition.
    # Rides prev_frame_guarded's safety condition; OFF -> prompts unchanged.
    bridge_shots: bool = False
    # Bring-your-own-key: when true, users MUST paste their own DashScope key
    # in Settings — the server key above is never used for their work. Set
    # this on any public deployment so visitors bill their own accounts.
    require_user_api_key: bool = False
    # International Qwen Cloud / Model Studio (Singapore). Use the China endpoints
    # (dashscope.aliyuncs.com) only if your key is from the China console.
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    # DashScope native API (async video generation lives here, not on compatible-mode)
    qwen_video_base_url: str = "https://dashscope-intl.aliyuncs.com/api/v1"
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_bucket_name: str = "rexgent-assets"
    oss_endpoint: str = "https://oss-ap-southeast-1.aliyuncs.com"
    database_url: str = "postgresql://rexgent:rexgent_dev@localhost:5432/rexgent"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-production"
    environment: str = "development"
    # Deployed frontend origin (e.g. http://47.x.x.x:3000 or https://rexgent.app)
    # — appended to the CORS allow-list alongside localhost.
    frontend_origin: str = ""

    # Neo4j (narrative graph)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "rexgent_dev"

    # Qwen-Max token cost (USD per 1k tokens) — for budget accounting
    qwen_max_input_cost_per_1k: float = 0.0016
    qwen_max_output_cost_per_1k: float = 0.0064

    # Production Bible: image generation/editing model IDs.
    # wan2.6-t2i uses the image-generation/generation endpoint + a messages array
    # (NOT the older text2image/image-synthesis prompt-string endpoint).
    qwen_image_model: str = "wan2.6-t2i"
    qwen_image_edit_model: str = "qwen-image-edit-max"
    qwen_vl_continuity_model: str = "qwen3-vl-plus"
    # Gates HappyHorse native-talk (the model speaks the scripted line itself and
    # syncs its own mouth; no audio is sent to the model). Flip false to disable
    # native-talk instantly — the fallback is a silent take with coverage framing.
    lipsync_enabled: bool = True
    qwen_image_path: str = "/services/aigc/image-generation/generation"
    # qwen-image-edit-max lives on the SYNCHRONOUS multimodal endpoint — the async
    # image-generation endpoint rejects it with InvalidParameter "url error".
    qwen_image_edit_path: str = "/services/aigc/multimodal-generation/generation"

    # Production Bible: TTS synthesis (restored for the TTS_OVERLAY mode).
    # qwen3-tts-flash is the OFFLINE model (simple SDK call, preset voices) — the DEFAULT
    # for dialogue + previews. Cloning is an EXTRA option: the user uploads a voice sample,
    # we enrol a custom voice via qwen-voice-enrollment, then synthesize it through the
    # qwen3-tts-vc-realtime WebSocket. A voice_model containing "realtime" routes to that path.
    qwen_tts_designed_model: str = "qwen3-tts-flash"
    # instruct variant: honors natural-language delivery directions
    # ("whispering, tearful") — same timbres, near-identical price
    qwen_tts_instruct_model: str = "qwen3-tts-instruct-flash"
    # voice design: a bespoke timbre from a text description ($0.2/voice),
    # synthesized with the vd snapshot model
    qwen_voice_design_model: str = "qwen-voice-design"
    qwen_tts_vd_model: str = "qwen3-tts-vd-2026-01-26"
    qwen_tts_preview_model: str = "qwen3-tts-flash"
    qwen_tts_cloned_model: str = "qwen3-tts-vc-realtime-2026-01-15"
    qwen_voice_enroll_model: str = "qwen-voice-enrollment"
    qwen_voice_enroll_path: str = "/services/audio/tts/customization"
    qwen_tts_realtime_url: str = "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
