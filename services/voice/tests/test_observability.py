from unittest.mock import MagicMock, patch

import pytest
from opentelemetry import metrics, trace

from voice.config import Settings
from voice.observability import get_meter, get_tracer, setup_telemetry


def _settings(endpoint: str = "") -> Settings:
    return Settings(otel_endpoint=endpoint)


class TestSetupTelemetryNoOp:
    def test_no_exception_with_empty_endpoint(self) -> None:
        tracer, meter = setup_telemetry(_settings(endpoint=""))
        assert tracer is not None
        assert meter is not None

    def test_returns_tracer_and_meter_tuple(self) -> None:
        result = setup_telemetry(_settings(endpoint=""))
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_tracer_is_usable(self) -> None:
        tracer, _ = setup_telemetry(_settings(endpoint=""))
        with tracer.start_as_current_span("test-span") as span:
            assert span is not None

    def test_meter_is_usable(self) -> None:
        _, meter = setup_telemetry(_settings(endpoint=""))
        counter = meter.create_counter("test.counter")
        counter.add(1)


class TestSetupTelemetryWithEndpoint:
    def test_no_exception_with_endpoint_set(self) -> None:
        with patch(
            "voice.observability.OTLPSpanExporter",
            return_value=MagicMock(),
        ), patch(
            "voice.observability.OTLPMetricExporter",
            return_value=MagicMock(),
        ):
            tracer, meter = setup_telemetry(_settings(endpoint="http://otel-collector:4317"))
        assert tracer is not None
        assert meter is not None

    def test_otlp_span_exporter_called_with_endpoint(self) -> None:
        endpoint = "http://otel-collector:4317"
        with patch(
            "voice.observability.OTLPSpanExporter",
            return_value=MagicMock(),
        ) as mock_exporter, patch(
            "voice.observability.OTLPMetricExporter",
            return_value=MagicMock(),
        ):
            setup_telemetry(_settings(endpoint=endpoint))
        mock_exporter.assert_called_once_with(endpoint=endpoint)

    def test_otlp_metric_exporter_called_with_endpoint(self) -> None:
        endpoint = "http://otel-collector:4317"
        with patch(
            "voice.observability.OTLPSpanExporter",
            return_value=MagicMock(),
        ), patch(
            "voice.observability.OTLPMetricExporter",
            return_value=MagicMock(),
        ) as mock_metric_exporter:
            setup_telemetry(_settings(endpoint=endpoint))
        mock_metric_exporter.assert_called_once_with(endpoint=endpoint)


class TestHistograms:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        setup_telemetry(_settings(endpoint=""))

    def test_stt_latency_histogram_recordable(self) -> None:
        meter = get_meter()
        hist = meter.create_histogram(
            "voice.stt.latency_seconds",
            description="STT transcription latency in seconds",
        )
        hist.record(0.42)

    def test_tts_latency_histogram_recordable(self) -> None:
        meter = get_meter()
        hist = meter.create_histogram(
            "voice.tts.latency_seconds",
            description="TTS synthesis latency in seconds",
        )
        hist.record(0.15)

    def test_bridge_latency_histogram_recordable(self) -> None:
        meter = get_meter()
        hist = meter.create_histogram(
            "voice.bridge.latency_seconds",
            description="NATS bridge round-trip latency in seconds",
        )
        hist.record(0.08)

    def test_turn_latency_histogram_recordable(self) -> None:
        meter = get_meter()
        hist = meter.create_histogram(
            "voice.turn.latency_seconds",
            description="Full turn pipeline latency in seconds",
        )
        hist.record(1.23)


class TestModuleAccessors:
    def test_get_tracer_returns_non_none_after_setup(self) -> None:
        setup_telemetry(_settings(endpoint=""))
        assert get_tracer() is not None

    def test_get_meter_returns_non_none_after_setup(self) -> None:
        setup_telemetry(_settings(endpoint=""))
        assert get_meter() is not None

    def test_get_tracer_returns_tracer_type(self) -> None:
        setup_telemetry(_settings(endpoint=""))
        tracer = get_tracer()
        assert isinstance(tracer, trace.Tracer)

    def test_get_meter_returns_meter_type(self) -> None:
        setup_telemetry(_settings(endpoint=""))
        meter = get_meter()
        assert isinstance(meter, metrics.Meter)

    def test_get_tracer_matches_setup_return(self) -> None:
        tracer, _ = setup_telemetry(_settings(endpoint=""))
        assert get_tracer() is tracer

    def test_get_meter_matches_setup_return(self) -> None:
        _, meter = setup_telemetry(_settings(endpoint=""))
        assert get_meter() is meter
