import logging
from typing import Any

import structlog
from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
    OTLPMetricExporter,
)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from sherlock.config import Settings


def configure_logging() -> None:
    """Configure structlog with JSON output for structured logging."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def init_telemetry(settings: Settings) -> None:
    """Initialize OTEL TracerProvider and MeterProvider with OTLP gRPC exporters."""
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


def instrument_app(app: FastAPI) -> None:
    """Apply FastAPI OTEL instrumentation."""
    FastAPIInstrumentor().instrument_app(app)


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
