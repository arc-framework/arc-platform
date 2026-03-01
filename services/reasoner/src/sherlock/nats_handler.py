import json
import time
from typing import Any, Optional

import nats
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg

from sherlock.config import Settings
from sherlock.graph import invoke_graph
from sherlock.observability import SherlockMetrics


class NATSHandler:
    """NATS request-reply subscriber for real-time reasoning requests.

    Subscribes to settings.nats_subject with queue group settings.nats_queue_group.
    Supports both request-reply (caller uses nc.request()) and fire-and-forget
    (caller uses nc.publish() without reply_to) patterns.
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
        self._nc: Optional[NATSClient] = None

    async def connect(self) -> None:
        """Establish NATS connection."""
        self._nc = await nats.connect(self._settings.nats_url)

    async def subscribe(self) -> None:
        """Subscribe to the request subject with queue group load balancing."""
        if self._nc is None:
            raise RuntimeError("NATSHandler.connect() must be called before subscribe()")
        await self._nc.subscribe(
            self._settings.nats_subject,
            queue=self._settings.nats_queue_group,
            cb=self._handle,
        )

    async def _handle(self, msg: Msg) -> None:
        """Process an incoming NATS message. Responds only if reply subject is set."""
        start = time.monotonic()
        self._metrics.requests_total.add(1, {"transport": "nats"})

        try:
            payload = json.loads(msg.data.decode())
            user_id: str = payload["user_id"]
            text: str = payload["text"]

            response = await invoke_graph(self._graph, self._memory, user_id, text)

            latency_ms = int((time.monotonic() - start) * 1000)
            self._metrics.latency.record(latency_ms, {"transport": "nats"})

            if msg.reply:
                result = json.dumps(
                    {"user_id": user_id, "text": response, "latency_ms": latency_ms}
                )
                await msg.respond(result.encode())

        except Exception as exc:
            self._metrics.errors_total.add(1, {"transport": "nats"})
            latency_ms = int((time.monotonic() - start) * 1000)

            if msg.reply:
                error_payload = json.dumps(
                    {"error": str(exc), "latency_ms": latency_ms}
                )
                await msg.respond(error_payload.encode())

    def is_connected(self) -> bool:
        """Return True if the NATS connection is active."""
        return self._nc is not None and self._nc.is_connected

    async def close(self) -> None:
        """Drain and close the NATS connection."""
        if self._nc is not None:
            await self._nc.drain()
            await self._nc.close()
            self._nc = None
