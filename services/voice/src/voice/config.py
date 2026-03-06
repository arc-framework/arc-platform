from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VOICE_",
        env_ignore_empty=False,
        extra="ignore",
    )

    # Speech providers
    stt_provider: str = "faster-whisper"
    tts_provider: str = "piper"

    # NATS bridge to arc-reasoner (matches arc.reasoner.request — Spec 015 final subject)
    bridge_nats_subject: str = "arc.reasoner.request"
    bridge_timeout_ms: int = 10000

    # LiveKit realtime server
    livekit_url: str = "ws://arc-realtime:7880"
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # OTEL — empty string disables exporter (no-op fallback)
    otel_endpoint: str = ""

    # Service
    port: int = 8803
    log_level: str = "INFO"

    # NATS server URL for health checks and bridge connectivity
    nats_url: str = "nats://arc-messaging:4222"

    # Piper TTS binary path (installed to /usr/local/bin/piper in Dockerfile)
    piper_bin: str = "/usr/local/bin/piper"

    # faster-whisper model tunables
    whisper_model: str = "tiny"
    whisper_device: str = "cpu"
