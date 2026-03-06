import pytest

from voice.config import Settings


def test_defaults_instantiate_with_no_env_vars():
    """Settings() must work with no env vars set."""
    s = Settings()
    assert s is not None


def test_default_stt_provider():
    s = Settings()
    assert s.stt_provider == "faster-whisper"


def test_default_tts_provider():
    s = Settings()
    assert s.tts_provider == "piper"


def test_default_bridge_nats_subject():
    s = Settings()
    assert s.bridge_nats_subject == "arc.reasoner.request"


def test_default_bridge_timeout_ms():
    s = Settings()
    assert s.bridge_timeout_ms == 10000


def test_default_livekit_url():
    s = Settings()
    assert s.livekit_url == "ws://arc-realtime:7880"


def test_default_livekit_api_key_empty():
    s = Settings()
    assert s.livekit_api_key == ""


def test_default_livekit_api_secret_empty():
    s = Settings()
    assert s.livekit_api_secret == ""


def test_default_otel_endpoint_empty():
    s = Settings()
    assert s.otel_endpoint == ""


def test_default_port():
    s = Settings()
    assert s.port == 8803


def test_default_log_level():
    s = Settings()
    assert s.log_level == "INFO"


def test_default_piper_bin():
    s = Settings()
    assert s.piper_bin == "/usr/local/bin/piper"


def test_default_whisper_model():
    s = Settings()
    assert s.whisper_model == "tiny"


def test_default_whisper_device():
    s = Settings()
    assert s.whisper_device == "cpu"


def test_env_override_port(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VOICE_PORT", "9000")
    s = Settings()
    assert s.port == 9000


def test_env_override_stt_provider(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VOICE_STT_PROVIDER", "openai-whisper")
    s = Settings()
    assert s.stt_provider == "openai-whisper"


def test_env_override_bridge_nats_subject(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VOICE_BRIDGE_NATS_SUBJECT", "custom.subject")
    s = Settings()
    assert s.bridge_nats_subject == "custom.subject"


def test_env_override_bridge_timeout_ms(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VOICE_BRIDGE_TIMEOUT_MS", "5000")
    s = Settings()
    assert s.bridge_timeout_ms == 5000


def test_env_override_livekit_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VOICE_LIVEKIT_URL", "wss://livekit.example.com")
    s = Settings()
    assert s.livekit_url == "wss://livekit.example.com"


def test_env_override_whisper_model(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VOICE_WHISPER_MODEL", "large")
    s = Settings()
    assert s.whisper_model == "large"


def test_env_override_whisper_device(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VOICE_WHISPER_DEVICE", "cuda")
    s = Settings()
    assert s.whisper_device == "cuda"


def test_env_override_log_level(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VOICE_LOG_LEVEL", "DEBUG")
    s = Settings()
    assert s.log_level == "DEBUG"
