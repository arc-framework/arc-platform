import pytest

from voice.config import Settings


@pytest.mark.parametrize(
    "field,expected",
    [
        ("stt_provider", "faster-whisper"),
        ("tts_provider", "piper"),
        ("bridge_nats_subject", "arc.reasoner.request"),
        ("bridge_timeout_ms", 10000),
        ("livekit_url", "ws://arc-realtime:7880"),
        ("livekit_api_key", ""),
        ("livekit_api_secret", ""),
        ("otel_endpoint", ""),
        ("port", 8803),
        ("log_level", "INFO"),
        ("piper_bin", "/usr/local/bin/piper"),
        ("whisper_model", "tiny"),
        ("whisper_device", "cpu"),
    ],
)
def test_defaults(field: str, expected: object) -> None:
    assert getattr(Settings(), field) == expected


@pytest.mark.parametrize(
    "env_var,field,value,cast",
    [
        ("VOICE_PORT", "port", "9000", int),
        ("VOICE_STT_PROVIDER", "stt_provider", "openai-whisper", str),
        ("VOICE_BRIDGE_NATS_SUBJECT", "bridge_nats_subject", "custom.subject", str),
        ("VOICE_BRIDGE_TIMEOUT_MS", "bridge_timeout_ms", "5000", int),
        ("VOICE_LIVEKIT_URL", "livekit_url", "wss://livekit.example.com", str),
        ("VOICE_WHISPER_MODEL", "whisper_model", "large", str),
        ("VOICE_WHISPER_DEVICE", "whisper_device", "cuda", str),
        ("VOICE_LOG_LEVEL", "log_level", "DEBUG", str),
    ],
)
def test_env_override(
    monkeypatch: pytest.MonkeyPatch,
    env_var: str,
    field: str,
    value: str,
    cast: type,
) -> None:
    monkeypatch.setenv(env_var, value)
    assert getattr(Settings(), field) == cast(value)
