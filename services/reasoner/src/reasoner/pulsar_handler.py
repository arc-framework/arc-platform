import asyncio
import contextlib
import json
import time
from typing import Any

import pulsar

from reasoner.config import Settings
from reasoner.graph import GraphErrorResponse, invoke_graph
from reasoner.models_v1 import InferenceCompletedEvent, RequestReceivedEvent, TokenUsage
from reasoner.observability import SherlockMetrics


class PulsarHandler:
    """Durable async Pulsar consumer for long-horizon reasoning tasks.

    Uses asyncio.to_thread() to bridge the synchronous pulsar-client C++ binding
    to the asyncio event loop. The consume loop runs as a background asyncio.Task,
    spawning a sub-task per message so slow inferences don't block message receipt.

    Failure path (two distinct outcomes — GAP-6 resolved):
      Path A — graph returned error string (error_handler exhausted retries):
        invoke_graph() returns a string; _process() publishes {"request_id": ...,
        "error": str, "latency_ms": N} to reasoner-results → consumer.acknowledge(msg)
        (successful processing of bad input — do NOT redeliver)

      Path B — unhandled exception (JSON decode failure, missing request_id, etc.):
        exception escapes → consumer.negative_acknowledge(msg)
        → Pulsar redelivers to another replica
    """

    def __init__(
        self,
        graph: Any,
        memory: Any,
        settings: Settings,
        metrics: SherlockMetrics,
    ) -> None:
        self._graph = graph
        self._memory = memory
        self._settings = settings
        self._metrics = metrics
        self._client: pulsar.Client | None = None
        self._consumer: Any | None = None
        self._producer: Any | None = None
        self._event_received_producer: Any | None = None
        self._event_completed_producer: Any | None = None
        self._task: asyncio.Task[None] | None = None

    def _connect(self) -> None:
        """Blocking connection setup (called via asyncio.to_thread)."""
        self._client = pulsar.Client(self._settings.pulsar_url)
        self._consumer = self._client.subscribe(
            self._settings.pulsar_request_topic,
            subscription_name=self._settings.pulsar_subscription,
            consumer_type=pulsar.ConsumerType.Shared,
        )
        self._producer = self._client.create_producer(
            self._settings.pulsar_result_topic
        )
        self._event_received_producer = self._client.create_producer(
            self._settings.pulsar_event_received_topic
        )
        self._event_completed_producer = self._client.create_producer(
            self._settings.pulsar_event_completed_topic
        )

    async def start(self) -> None:
        """Connect to Pulsar and start the background consume loop."""
        await asyncio.to_thread(self._connect)
        self._task = asyncio.create_task(self._consume_loop())

    async def _consume_loop(self) -> None:
        """Receive messages in a loop; spawn a task per message for concurrent processing."""
        while True:
            try:
                # Non-blocking via thread — 5s timeout allows clean shutdown
                msg = await asyncio.to_thread(
                    self._consumer.receive, timeout_millis=5_000
                )
                if msg is not None:
                    asyncio.create_task(self._process(msg))
            except Exception:
                # Timeout or transient error — continue loop
                continue

    async def _publish_event(self, producer: Any, payload_bytes: bytes) -> None:
        """Fire-and-forget Pulsar event publish (best-effort, never raises)."""
        try:
            if producer is not None:
                await asyncio.to_thread(producer.send, payload_bytes)
        except Exception:
            pass

    async def _process(self, msg: Any) -> None:
        """Process a single Pulsar message.

        Publishes RequestReceivedEvent before processing (TASK-031) and
        InferenceCompletedEvent after successful inference (TASK-033).

        Path A — GraphErrorResponse (error_handler exhausted retries):
            invoke_graph raises GraphErrorResponse; _process publishes
            {"request_id":..., "error": str, "latency_ms": N} to reasoner-results
            → consumer.acknowledge(msg). Message was successfully processed.

        Path B — unhandled exception (JSON decode failure, missing request_id, etc.):
            exception escapes → consumer.negative_acknowledge(msg)
            → Pulsar redelivers to another replica.
        """
        start = time.monotonic()
        self._metrics.requests_total.add(1, {"transport": "pulsar"})

        try:
            payload = json.loads(msg.data().decode())
            request_id: str = payload["request_id"]   # KeyError → outer except → Path B
            user_id: str = payload["user_id"]
            text: str = payload["text"]

            # T031: Publish request.received before any processing (fire-and-forget)
            asyncio.create_task(
                self._publish_event(
                    self._event_received_producer,
                    RequestReceivedEvent(
                        request_id=request_id,
                        user_id=user_id,
                        subject=self._settings.pulsar_request_topic,
                    ).model_dump_json().encode(),
                )
            )

            try:
                response = await invoke_graph(self._graph, self._memory, user_id, text)
            except GraphErrorResponse as graph_err:
                # Path A: graph returned graceful error (error_handler exhausted retries)
                latency_ms = int((time.monotonic() - start) * 1000)
                error_result: dict[str, Any] = {
                    "request_id": request_id,
                    "error": graph_err.error_message,
                    "latency_ms": latency_ms,
                }
                await asyncio.to_thread(
                    self._producer.send, json.dumps(error_result).encode()
                )
                await asyncio.to_thread(self._consumer.acknowledge, msg)
                self._metrics.errors_total.add(1, {"transport": "pulsar"})
                return

            latency_ms = int((time.monotonic() - start) * 1000)
            result: dict[str, Any] = {
                "request_id": request_id,
                "user_id": user_id,
                "text": response,
                "latency_ms": latency_ms,
            }
            await asyncio.to_thread(
                self._producer.send, json.dumps(result).encode()
            )
            await asyncio.to_thread(self._consumer.acknowledge, msg)
            self._metrics.latency.record(latency_ms, {"transport": "pulsar"})

            # T033: Publish inference.completed with token usage (fire-and-forget)
            input_tokens = max(1, len(text.split()))
            output_tokens = max(1, len(response.split()))
            asyncio.create_task(
                self._publish_event(
                    self._event_completed_producer,
                    InferenceCompletedEvent(
                        request_id=request_id,
                        user_id=user_id,
                        model=self._settings.llm_model,
                        latency_ms=latency_ms,
                        usage=TokenUsage(
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            total_tokens=input_tokens + output_tokens,
                        ),
                    ).model_dump_json().encode(),
                )
            )

        except Exception:
            # Path B: unhandled exception — nack so Pulsar can redeliver
            self._metrics.errors_total.add(1, {"transport": "pulsar"})
            await asyncio.to_thread(self._consumer.negative_acknowledge, msg)

    async def close(self) -> None:
        """Cancel the consume task and close the Pulsar client."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._client is not None:
            await asyncio.to_thread(self._client.close)
