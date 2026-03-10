"""Shared pytest fixtures and session-level OTEL initialisation."""

from __future__ import annotations

import pytest

from voice.config import Settings
from voice.observability import setup_telemetry


@pytest.fixture(scope="session", autouse=True)
def _init_telemetry() -> None:
    """Initialise OTEL with no-op exporters once for the whole test session.

    This ensures get_tracer() / get_stt_histogram() etc. never raise
    RuntimeError("setup_telemetry() has not been called") in test code.
    """
    setup_telemetry(Settings())
