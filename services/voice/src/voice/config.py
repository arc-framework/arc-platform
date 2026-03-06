from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VOICE_",
        env_ignore_empty=False,
        extra="ignore",
    )

    # Speech providers
    stt_provider: str = Field("faster-whisper", alias="VOICE_STT_PROVIDER")
    tts_provider: str = Field("piper", alias="VOICE_TTS_PROVIDER")

    # NATS bridge to arc-reasoner (matches arc.reasoner.request — Spec 015 final subject)
    bridge_nats_subject: str = Field("arc.reasoner.request", alias="VOICE_BRIDGE_NATS_SUBJECT")
    bridge_timeout_ms: int = Field(10000, alias="VOICE_BRIDGE_TIMEOUT_MS")

    # LiveKit realtime server
    livekit_url: str = Field("ws://arc-realtime:7880", alias="VOICE_LIVEKIT_URL")
    livekit_api_key: str = Field("", alias="VOICE_LIVEKIT_API_KEY")
    livekit_api_secret: str = Field("", alias="VOICE_LIVEKIT_API_SECRET")

    # OTEL — empty string disables exporter (no-op fallback)
    otel_endpoint: str = Field("", alias="VOICE_OTEL_ENDPOINT")

    # Service
    port: int = Field(8803, alias="VOICE_PORT")
    log_level: str = Field("INFO", alias="VOICE_LOG_LEVEL")

    # Piper TTS binary path (installed to /usr/local/bin/piper in Dockerfile)
    piper_bin: str = Field("/usr/local/bin/piper", alias="VOICE_PIPER_BIN")

    # faster-whisper model tunables
    whisper_model: str = Field("tiny", alias="VOICE_WHISPER_MODEL")
    whisper_device: str = Field("cpu", alias="VOICE_WHISPER_DEVICE")
