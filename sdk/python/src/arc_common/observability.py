"""Shared OTEL + structlog setup for A.R.C. Platform Python services.

Usage in a new service:

    from arc_common.observability import configure_logging, init_telemetry

    configure_logging()   # call before any logging
    init_telemetry(
        endpoint="http://arc-friday-collector:4317",
        service_name="arc-myservice",
        service_version="0.1.0",
    )

Log event taxonomy — use the event type as the first positional arg.
structlog outputs it as `"event": ...` in JSON (stdout) and as `body` in OTEL/SigNoz.
SigNoz queries filter on body or attributes across all services:

    _log.debug("method_invocation", handler="my_handler")
    _log.info ("http_request",      status=200, latency_ms=12)
    _log.debug("service_call",      service="postgres", latency_ms=5)
    _log.debug("message_received",  subject="topic.name")
    _log.warning("exception",       error="...")
    _log.error  ("exception",       error="...", exc_info=True)
"""

from __future__ import annotations

import json as _json
import logging
import os
import time as _time
from typing import Any

import structlog
from opentelemetry import metrics, trace
from opentelemetry._logs import LogRecord as OTELLogRecord, SeverityNumber, set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# ─── Severity mapping ─────────────────────────────────────────────────────────

_LEVEL_TO_SEVERITY: dict[int, SeverityNumber] = {
    logging.DEBUG: SeverityNumber.DEBUG,
    logging.INFO: SeverityNumber.INFO,
    logging.WARNING: SeverityNumber.WARN,
    logging.ERROR: SeverityNumber.ERROR,
    logging.CRITICAL: SeverityNumber.FATAL,
}

# Fields that are structlog/OTEL meta — not emitted as log attributes.
_STRUCTLOG_META = frozenset({
    "event", "level", "timestamp", "logger",
    "_logger", "_name", "trace_id", "span_id",
})


# ─── Trace-context injection ──────────────────────────────────────────────────

def _inject_trace_context(
    _logger: Any, _method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Structlog processor: inject trace_id / span_id from the active OTEL span.

    When a span is active every log line gains trace_id and span_id fields.
    In SigNoz you can click any log line and jump directly to the correlated trace.
    """
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


# ─── OTEL log bridge ─────────────────────────────────────────────────────────

class _OTELStructlogHandler(logging.Handler):
    """Structlog-aware OTEL log bridge.

    structlog's ProcessorFormatter serialises the event_dict to a JSON string
    and mutates record.msg before any handler runs — so the SDK's LoggingHandler
    would ship the whole blob as body with no structured attributes.

    This handler parses that JSON back so that:
      • body       = the event string  (e.g. "http_request", "exception")
      • attributes = remaining kv pairs (method, path, status, latency_ms, …)

    Falls back gracefully for non-structlog records (uvicorn, sqlalchemy, …).
    """

    def __init__(self, logger_provider: LoggerProvider, level: int = logging.INFO) -> None:
        super().__init__(level)
        self._lp = logger_provider

    def emit(self, record: logging.LogRecord) -> None:
        try:
            raw = record.getMessage()
            try:
                event_dict = _json.loads(raw)
                body = str(event_dict.get("event", raw))
                attrs: dict[str, Any] = {
                    k: str(v)
                    for k, v in event_dict.items()
                    if k not in _STRUCTLOG_META
                }
            except (_json.JSONDecodeError, TypeError, ValueError):
                body = raw
                attrs = {}

            span_ctx = trace.get_current_span().get_span_context()
            otel_logger = self._lp.get_logger(record.name)
            otel_logger.emit(
                OTELLogRecord(
                    timestamp=int(record.created * 1e9),
                    observed_timestamp=_time.time_ns(),
                    trace_id=span_ctx.trace_id if span_ctx.is_valid else 0,
                    span_id=span_ctx.span_id if span_ctx.is_valid else 0,
                    trace_flags=span_ctx.trace_flags if span_ctx.is_valid else None,
                    body=body,
                    severity_text=record.levelname,
                    severity_number=_LEVEL_TO_SEVERITY.get(record.levelno, SeverityNumber.INFO),
                    attributes=attrs,
                )
            )
        except Exception:
            self.handleError(record)


# ─── Logging setup ────────────────────────────────────────────────────────────

def configure_logging(*, quiet: list[str] | None = None) -> None:
    """Configure structured JSON logging to stdout with trace-context injection.

    Reads LOG_LEVEL from the environment (default: info).
    Mirrors Cortex's TeeHandler pattern — init_telemetry() can later attach an
    OTLP handler to the same root logger (stdout + SigNoz).

    Args:
        quiet: extra logger names to silence to WARNING (e.g. heavy libraries).
    """
    _level = getattr(logging, os.environ.get("LOG_LEVEL", "info").upper(), logging.INFO)

    shared_pre_chain: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _inject_trace_context,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

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
    root.setLevel(_level)

    for name in (quiet or []):
        logging.getLogger(name).setLevel(logging.WARNING)

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

def init_telemetry(
    *,
    endpoint: str,
    service_name: str,
    service_version: str,
    traces_enabled: bool = True,
    metrics_enabled: bool = True,
    logs_enabled: bool = True,
) -> None:
    """Initialise OTEL providers. Non-fatal: unreachable collector doesn't block startup.

    Signals shipped to the collector endpoint:
      • Traces  — when traces_enabled (default True)
      • Metrics — when metrics_enabled (default True)
      • Logs    — when logs_enabled (default True) — root stdlib handler → OTLP gRPC
    """
    resource = Resource.create({SERVICE_NAME: service_name, SERVICE_VERSION: service_version})

    if traces_enabled:
        tp = TracerProvider(resource=resource)
        tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(tp)

    if metrics_enabled:
        mp = MeterProvider(
            resource=resource,
            metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint))],
        )
        metrics.set_meter_provider(mp)

    if logs_enabled:
        lp = LoggerProvider(resource=resource)
        lp.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint)))
        set_logger_provider(lp)
        # Structlog-aware bridge: parses the JSON body structlog emits so that
        # body=event_string and attributes=kv_pairs reach SigNoz correctly.
        logging.root.addHandler(_OTELStructlogHandler(logger_provider=lp, level=logging.INFO))
