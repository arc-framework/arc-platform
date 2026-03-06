"""OTEL tracer, meter, and per-stage histograms for the voice service (Scarlett)."""

from collections.abc import Sequence

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.metrics import Histogram, Meter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Tracer

from voice.config import Settings


class _NoOpSpanExporter(SpanExporter):
    """Span exporter that discards all spans — used when no OTEL endpoint is set."""

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass

# ─── Module-level singletons ──────────────────────────────────────────────────

_tracer: Tracer | None = None
_meter: Meter | None = None

# ─── Per-stage histograms ─────────────────────────────────────────────────────

stt_latency: Histogram | None = None
tts_latency: Histogram | None = None
bridge_latency: Histogram | None = None
turn_latency: Histogram | None = None


# ─── Setup ───────────────────────────────────────────────────────────────────

def setup_telemetry(settings: Settings) -> tuple[Tracer, Meter]:
    """Configure OTEL providers and return the tracer and meter.

    When ``settings.otel_endpoint`` is empty a no-op exporter is used so the
    service starts cleanly without a collector.  When an endpoint is provided
    the OTLP gRPC exporters are configured for both traces and metrics.
    """
    global _tracer, _meter
    global stt_latency, tts_latency, bridge_latency, turn_latency

    resource = Resource.create(
        {
            SERVICE_NAME: "arc-voice",
            SERVICE_VERSION: "0.1.0",
        }
    )

    # ── Traces ────────────────────────────────────────────────────────────────
    span_exporter: SpanExporter
    if settings.otel_endpoint:
        span_exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)
    else:
        span_exporter = _NoOpSpanExporter()

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    # ── Metrics ───────────────────────────────────────────────────────────────
    if settings.otel_endpoint:
        metric_exporter = OTLPMetricExporter(endpoint=settings.otel_endpoint)
        reader = PeriodicExportingMetricReader(metric_exporter)
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    else:
        meter_provider = MeterProvider(resource=resource)

    metrics.set_meter_provider(meter_provider)

    # ── Instruments ───────────────────────────────────────────────────────────
    meter = metrics.get_meter("arc-voice")

    stt_latency = meter.create_histogram(
        "voice.stt.latency_seconds",
        description="STT transcription latency in seconds",
    )
    tts_latency = meter.create_histogram(
        "voice.tts.latency_seconds",
        description="TTS synthesis latency in seconds",
    )
    bridge_latency = meter.create_histogram(
        "voice.bridge.latency_seconds",
        description="NATS bridge round-trip latency in seconds",
    )
    turn_latency = meter.create_histogram(
        "voice.turn.latency_seconds",
        description="Full turn pipeline latency in seconds",
    )

    tracer = trace.get_tracer("arc-voice")

    _tracer = tracer
    _meter = meter

    return tracer, meter


# ─── Module-level accessors ───────────────────────────────────────────────────

def get_tracer() -> Tracer:
    """Return the last tracer configured by ``setup_telemetry``."""
    if _tracer is None:
        raise RuntimeError("setup_telemetry() has not been called")
    return _tracer


def get_meter() -> Meter:
    """Return the last meter configured by ``setup_telemetry``."""
    if _meter is None:
        raise RuntimeError("setup_telemetry() has not been called")
    return _meter
