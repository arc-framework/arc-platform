import asyncio
import json
import time
from typing import Any, Optional

import pulsar

from sherlock.config import Settings
from sherlock.graph import GraphErrorResponse, invoke_graph
from sherlock.observability import SherlockMetrics


class PulsarHandler:
    """Durable async Pulsar consumer for long-horizon reasoning tasks.

    Uses asyncio.to_thread() to bridge the synchronous pulsar-client C++ binding
    to the asyncio event loop. The consume loop runs as a background asyncio.Task,
    spawning a sub-task per message so slow inferences don't block message receipt.

    Failure path (two distinct outcomes — GAP-6 resolved):
      Path A — graph returned error string (error_handler exhausted retries):
        invoke_graph() returns a string; _process() publishes {"request_id": ...,
        "error": str, "latency_ms": N} to sherlock-results → consumer.acknowledge(msg)
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
        self._client: Optional[pulsar.Client] = None
        self._consumer: Optional[Any] = None
        self._producer: Optional[Any] = None
        self._task: Optional[asyncio.Task[None]] = None

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

    async def _process(self, msg: Any) -> None:
        """Process a single Pulsar message.

        Path A — GraphErrorResponse (error_handler exhausted retries):
            invoke_graph raises GraphErrorResponse; _process publishes
            {"request_id":..., "error": str, "latency_ms": N} to sherlock-results
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

            try:
                response = await invoke_graph(self._graph, self._memory, user_id, text)
            except GraphErrorResponse as graph_err:
                # Path A: graph returned graceful error (error_handler exhausted retries)
                # Publish error result to sherlock-results and ACK — do NOT redeliver
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

        except Exception:
            # Path B: unhandled exception — nack so Pulsar can redeliver
            self._metrics.errors_total.add(1, {"transport": "pulsar"})
            await asyncio.to_thread(self._consumer.negative_acknowledge, msg)

    async def close(self) -> None:
        """Cancel the consume task and close the Pulsar client."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._client is not None:
            await asyncio.to_thread(self._client.close)
