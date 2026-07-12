from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    qwen_api_key: str = ""
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
    # Wan lip-sync (first_frame + driving_audio on eligible shots). Flip to
    # false to disable instantly — the fallback path is today's renderer.
    lipsync_enabled: bool = True
    qwen_image_path: str = "/services/aigc/image-generation/generation"
    # qwen-image-edit-max lives on the SYNCHRONOUS multimodal endpoint — the async
    # image-generation endpoint rejects it with InvalidParameter "url error".
    qwen_image_edit_path: str = "/services/aigc/multimodal-generation/generation"

    # Production Bible: TTS synthesis.
    # qwen3-tts-flash is the OFFLINE model (simple SDK call, preset voices) — the DEFAULT
    # for dialogue + previews. Cloning is an EXTRA option: the user uploads a voice sample,
    # we enrol a custom voice via qwen-voice-enrollment, then synthesize it through the
    # qwen3-tts-vc-realtime WebSocket. A voice_model containing "realtime" routes to that path.
    qwen_tts_designed_model: str = "qwen3-tts-flash"
    # instruct variant: honors natural-language delivery directions
    # ("whispering, tearful") — same timbres, near-identical price
    qwen_tts_instruct_model: str = "qwen3-tts-instruct-flash"
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
