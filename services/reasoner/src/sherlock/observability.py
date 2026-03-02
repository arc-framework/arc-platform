import logging
from typing import Any

import structlog
from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from sherlock.config import Settings

# ─── Trace-context injection ──────────────────────────────────────────────────

def _inject_trace_context(
    _logger: Any, _method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Structlog processor: inject trace_id / span_id from the active OTEL span.

    When a span is active (e.g. inside a FastAPI request), every log line
    emitted through structlog gains trace_id and span_id fields.  In SigNoz
    you can click any log line and jump directly to the correlated trace.
    """
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


# ─── Logging setup ────────────────────────────────────────────────────────────

def configure_logging() -> None:
    """Configure structured logging: JSON to stdout with trace-context injection.

    Uses structlog.stdlib.LoggerFactory so every log record flows through
    Python's stdlib logging.  init_telemetry() later attaches an
    OTLPLogExporter handler to the same root logger — mirroring Cortex's
    TeeHandler pattern (stdout + Friday/SigNoz).
    """
    # Processors that run on *all* records (structlog-native and foreign stdlib).
    shared_pre_chain: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _inject_trace_context,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    # Stdout handler: JSON renderer via ProcessorFormatter.
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
            foreign_pre_chain=shared_pre_chain,
        )
    )

    root = logging.getLogger()
    root.handlers = [stdout_handler]
    root.setLevel(logging.INFO)

    # Quiet noisy library loggers that add no signal.
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            *shared_pre_chain,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


# ─── Telemetry (traces + metrics + logs) ─────────────────────────────────────

def init_telemetry(settings: Settings) -> None:
    """Initialize OTEL providers.  Non-fatal: an unreachable collector does not
    block startup — exporters reconnect automatically.

    Signals shipped to arc-friday-collector:
      • Traces  — when otel_traces_enabled
      • Metrics — when otel_metrics_enabled
      • Logs    — when otel_logs_enabled (root stdlib handler → OTLP gRPC)
    """
    resource = Resource.create(
        {
            SERVICE_NAME: settings.service_name,
            SERVICE_VERSION: settings.service_version,
        }
    )

    if settings.otel_traces_enabled:
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_endpoint))
        )
        trace.set_tracer_provider(tracer_provider)

    if settings.otel_metrics_enabled:
        reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=settings.otel_endpoint)
        )
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(meter_provider)

    if settings.otel_logs_enabled:
        log_provider = LoggerProvider(resource=resource)
        log_provider.add_log_record_processor(
            BatchLogRecordProcessor(OTLPLogExporter(endpoint=settings.otel_endpoint))
        )
        set_logger_provider(log_provider)

        # Bridge: root stdlib logger → OTEL log pipeline.
        # Because configure_logging() switched structlog to stdlib.LoggerFactory,
        # ALL log records (structlog, uvicorn, sqlalchemy, asyncpg) now flow through
        # stdlib and are captured here — same as Cortex's TeeHandler.
        otel_handler = LoggingHandler(logger_provider=log_provider, level=logging.INFO)
        logging.root.addHandler(otel_handler)


# ─── FastAPI instrumentation ──────────────────────────────────────────────────

def instrument_app(app: FastAPI) -> None:
    """Apply OTEL FastAPI auto-instrumentation (creates a span per request)."""
    FastAPIInstrumentor().instrument_app(app)


# ─── Content-tracing gate ─────────────────────────────────────────────────────

def add_span_content_attributes(
    span: Any,
    *,
    user_message: str,
    assistant_message: str,
    content_tracing: bool,
) -> None:
    """Conditionally add message content to a span (SHERLOCK_CONTENT_TRACING gate).

    When content_tracing is False (default), no PII is emitted to traces.
    """
    if not content_tracing:
        return
    span.set_attribute("user_message", user_message)
    span.set_attribute("assistant_message", assistant_message)


# ─── Metrics instruments ──────────────────────────────────────────────────────

class SherlockMetrics:
    """OTEL metrics instruments for the Sherlock service."""

    def __init__(self) -> None:
        meter = metrics.get_meter("arc-sherlock")

        self.requests_total = meter.create_counter(
            "sherlock.requests.total",
            description="Total number of reasoning requests",
        )
        self.errors_total = meter.create_counter(
            "sherlock.errors.total",
            description="Total number of failed reasoning requests",
        )
        self.latency = meter.create_histogram(
            "sherlock.latency",
            description="Reasoning request latency in milliseconds",
            unit="ms",
        )
        self.context_size = meter.create_histogram(
            "sherlock.context.size",
            description="Number of context chunks retrieved per request",
        )
