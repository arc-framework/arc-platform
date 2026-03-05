"""Tests for observability.py — GAP-5: content_tracing security default verification."""
from __future__ import annotations

import os
from unittest.mock import MagicMock


# ─── GAP-5 Tests: SHERLOCK_CONTENT_TRACING security default ───────────────────


def test_content_tracing_default_false(monkeypatch: object) -> None:
    """SHERLOCK_CONTENT_TRACING defaults to False when env var is unset.

    This is the security default: no PII is emitted to traces unless explicitly
    opted in by setting SHERLOCK_CONTENT_TRACING=true.
    """
    # Ensure the var is absent from the environment
    import os as _os
    _os.environ.pop("SHERLOCK_CONTENT_TRACING", None)

    # Re-instantiate Settings to pick up clean env
    from reasoner.config import Settings

    settings = Settings()
    assert settings.content_tracing is False, (
        "SHERLOCK_CONTENT_TRACING must default to False — "
        "content must not appear in traces unless explicitly enabled"
    )


def test_content_tracing_env_override() -> None:
    """Setting SHERLOCK_CONTENT_TRACING=true overrides the default to True."""
    original = os.environ.get("SHERLOCK_CONTENT_TRACING")
    try:
        os.environ["SHERLOCK_CONTENT_TRACING"] = "true"

        # Import Settings fresh after setting the env var
        from reasoner.config import Settings

        settings = Settings()
        assert settings.content_tracing is True, (
            "SHERLOCK_CONTENT_TRACING=true must result in content_tracing=True"
        )
    finally:
        # Restore env state
        if original is None:
            os.environ.pop("SHERLOCK_CONTENT_TRACING", None)
        else:
            os.environ["SHERLOCK_CONTENT_TRACING"] = original


def test_otel_span_no_content_when_disabled() -> None:
    """When content_tracing=False, add_span_content_attributes adds no attributes.

    Verifies that message content (potential PII) is never emitted to OTEL spans
    unless the operator explicitly enables content tracing.
    """
    from reasoner.observability import add_span_content_attributes

    mock_span = MagicMock()

    add_span_content_attributes(
        mock_span,
        user_message="What is the weather?",
        assistant_message="It is sunny today.",
        content_tracing=False,
    )

    # Span must not have any attributes set when content_tracing=False
    mock_span.set_attribute.assert_not_called(), (
        "No span attributes should be set when content_tracing=False"
    )


def test_otel_span_content_when_enabled() -> None:
    """When content_tracing=True, message content is added to spans."""
    from reasoner.observability import add_span_content_attributes

    mock_span = MagicMock()

    add_span_content_attributes(
        mock_span,
        user_message="What is the weather?",
        assistant_message="It is sunny today.",
        content_tracing=True,
    )

    mock_span.set_attribute.assert_any_call("user_message", "What is the weather?")
    mock_span.set_attribute.assert_any_call("assistant_message", "It is sunny today.")


def test_ttft_histogram_registered() -> None:
    """SherlockMetrics registers the reasoner.ttft.seconds histogram instrument."""
    from unittest.mock import MagicMock, patch

    mock_meter = MagicMock()
    mock_histogram = MagicMock()
    mock_meter.create_histogram.return_value = mock_histogram

    with patch("reasoner.observability.metrics") as mock_metrics_module:
        mock_metrics_module.get_meter.return_value = mock_meter

        from reasoner.observability import SherlockMetrics
        m = SherlockMetrics()

    # Verify ttft histogram was created with correct name and unit
    histogram_calls = {
        call.args[0]: call.kwargs
        for call in mock_meter.create_histogram.call_args_list
    }
    assert "reasoner.ttft.seconds" in histogram_calls, (
        "SherlockMetrics must register 'reasoner.ttft.seconds' histogram"
    )
    assert histogram_calls["reasoner.ttft.seconds"].get("unit") == "s", (
        "reasoner.ttft.seconds must use unit='s'"
    )
    assert m.ttft_seconds is mock_histogram
