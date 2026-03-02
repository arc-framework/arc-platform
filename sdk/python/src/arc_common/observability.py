"""Shared OTEL + structlog setup for A.R.C. Platform Python services.

Usage in a new service:

    from arc_common.observability import configure_logging, init_telemetry

    configure_logging()   # call before any logging
    init_telemetry(
        endpoint="http://arc-friday-collector:4317",
        service_name="arc-myservice",
        service_version="0.1.0",
    )

Log event taxonomy — use the event type as the first positional arg (structlog outputs it
as `"event": ...` in JSON). SigNoz queries filter on the event field across all services:

    _log.debug("method_invocation", handler="my_handler")
    _log.info ("http_request",      status=200, latency_ms=12)
    _log.debug("service_call",      service="postgres", latency_ms=5)
    _log.debug("message_received",  subject="topic.name")
    _log.warning("exception",       error="...")
    _log.error  ("exception",       error="...", exc_info=True)
"""

from __future__ import annotations

import logging
import os
from typing import Any

import structlog
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


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
        logging.root.addHandler(LoggingHandler(logger_provider=lp, level=logging.INFO))
