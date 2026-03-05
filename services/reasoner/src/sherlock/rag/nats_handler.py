"""RAG NATS handler — subscribes to sherlock.v1.rag.* subjects."""
from __future__ import annotations

import json
import time
from typing import Any

import nats
import structlog
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg

from sherlock.config import Settings
from sherlock.graph import invoke_graph
from sherlock.memory import SherlockMemory
from sherlock.rag.store import RAGInfra

_log = structlog.get_logger(__name__)

_SUBJECT_INGEST_REQ = "sherlock.v1.rag.ingest.request"
_SUBJECT_INGEST_RES = "sherlock.v1.rag.ingest.result"
_SUBJECT_SEARCH_REQ = "sherlock.v1.rag.search.request"
_SUBJECT_SEARCH_RES = "sherlock.v1.rag.search.result"
_SUBJECT_EMBED_REQ = "sherlock.v1.rag.embed.request"
_SUBJECT_EMBED_RES = "sherlock.v1.rag.embed.result"
_SUBJECT_CHAT_REQ = "sherlock.v1.rag.chat.request"
_SUBJECT_CHAT_RES = "sherlock.v1.rag.chat.result"


class RAGNATSHandler:
    """NATS subscriber for RAG subjects (ingest, search, embed, chat).

    Subscribes to the four sherlock.v1.rag.* request subjects with the
    shared queue group for load balancing. Supports both request-reply
    (caller uses nc.request()) and fire-and-forget patterns.
    """

    def __init__(
        self,
        rag: RAGInfra,
        graph: Any,
        memory: SherlockMemory,
        settings: Settings,
    ) -> None:
        self._rag = rag
        self._graph = graph
        self._memory = memory
        self._settings = settings
        self._nc: NATSClient | None = None

    async def connect(self) -> None:
        """Establish NATS connection."""
        self._nc = await nats.connect(self._settings.nats_url)

    async def subscribe(self) -> None:
        """Subscribe to all RAG request subjects."""
        if self._nc is None:
            raise RuntimeError("RAGNATSHandler.connect() must be called before subscribe()")
        await self._nc.subscribe(
            _SUBJECT_INGEST_REQ,
            queue=self._settings.nats_queue_group,
            cb=self._handle_ingest,
        )
        await self._nc.subscribe(
            _SUBJECT_SEARCH_REQ,
            queue=self._settings.nats_queue_group,
            cb=self._handle_search,
        )
        await self._nc.subscribe(
            _SUBJECT_EMBED_REQ,
            queue=self._settings.nats_queue_group,
            cb=self._handle_embed,
        )
        await self._nc.subscribe(
            _SUBJECT_CHAT_REQ,
            queue=self._settings.nats_queue_group,
            cb=self._handle_chat,
        )

    async def _publish(self, reply: str | None, result_subject: str, payload: bytes) -> None:
        """Respond to the caller (if request-reply) and publish to the result subject."""
        if self._nc is None:
            return
        if reply:
            await self._nc.publish(reply, payload)
        await self._nc.publish(result_subject, payload)

    async def _handle_ingest(self, msg: Msg) -> None:
        """Handle sherlock.v1.rag.ingest.request → IngestPipeline.ingest."""
        start = time.monotonic()
        _log.debug(
            f"nats rag recv: {msg.subject}",
            event_type="message_received",
            subject=msg.subject,
            transport="nats",
        )
        try:
            payload = json.loads(msg.data.decode())
            file_id: str = payload["file_id"]
            vs_id: str = payload["vs_id"]

            chunk_count = await self._rag.ingest_pipeline.ingest(file_id, vs_id)
            latency_ms = int((time.monotonic() - start) * 1000)

            result = json.dumps({"status": "completed", "chunk_count": chunk_count}).encode()
            _log.info(
                "rag.ingest.done",
                file_id=file_id,
                vs_id=vs_id,
                chunk_count=chunk_count,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            _log.error(
                f"rag nats ingest error: {type(exc).__name__}",
                event_type="exception",
                error=str(exc),
                transport="nats",
                latency_ms=latency_ms,
            )
            result = json.dumps({"status": "failed", "error": str(exc)}).encode()

        await self._publish(msg.reply, _SUBJECT_INGEST_RES, result)

    async def _handle_search(self, msg: Msg) -> None:
        """Handle sherlock.v1.rag.search.request → HybridRetriever.search."""
        start = time.monotonic()
        _log.debug(
            f"nats rag recv: {msg.subject}",
            event_type="message_received",
            subject=msg.subject,
            transport="nats",
        )
        try:
            payload = json.loads(msg.data.decode())
            query: str = payload["query"]
            vs_ids: list[str] = payload["vs_ids"]
            alpha: float = float(payload.get("alpha", self._settings.hybrid_alpha))
            top_k: int = int(payload.get("top_k", self._settings.retrieval_top_k))
            candidate_k: int = int(
                payload.get("candidate_k", self._settings.retrieval_candidate_k)
            )

            search_results = await self._rag.retriever.search(
                query=query,
                vs_ids=vs_ids,
                alpha=alpha,
                candidate_k=candidate_k,
                top_k=top_k,
            )
            latency_ms = int((time.monotonic() - start) * 1000)

            results_payload = [
                {"chunk_id": r.chunk_id, "content": r.content, "score": r.score}
                for r in search_results
            ]
            result = json.dumps({"results": results_payload}).encode()
            _log.info(
                "rag.search.done",
                query_len=len(query),
                vs_count=len(vs_ids),
                result_count=len(search_results),
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            _log.error(
                f"rag nats search error: {type(exc).__name__}",
                event_type="exception",
                error=str(exc),
                transport="nats",
                latency_ms=latency_ms,
            )
            result = json.dumps({"error": str(exc)}).encode()

        await self._publish(msg.reply, _SUBJECT_SEARCH_RES, result)

    async def _handle_embed(self, msg: Msg) -> None:
        """Handle sherlock.v1.rag.embed.request → EmbedderAdapter.encode."""
        start = time.monotonic()
        _log.debug(
            f"nats rag recv: {msg.subject}",
            event_type="message_received",
            subject=msg.subject,
            transport="nats",
        )
        try:
            payload = json.loads(msg.data.decode())
            raw_input = payload["input"]
            texts: list[str] = [raw_input] if isinstance(raw_input, str) else list(raw_input)

            embeddings = self._rag.embedder.encode(texts)
            latency_ms = int((time.monotonic() - start) * 1000)

            result = json.dumps({"embeddings": embeddings}).encode()
            _log.info(
                "rag.embed.done",
                text_count=len(texts),
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            _log.error(
                f"rag nats embed error: {type(exc).__name__}",
                event_type="exception",
                error=str(exc),
                transport="nats",
                latency_ms=latency_ms,
            )
            result = json.dumps({"error": str(exc)}).encode()

        await self._publish(msg.reply, _SUBJECT_EMBED_RES, result)

    async def _handle_chat(self, msg: Msg) -> None:
        """Handle sherlock.v1.rag.chat.request → graph with vector_store_ids."""
        start = time.monotonic()
        _log.debug(
            f"nats rag recv: {msg.subject}",
            event_type="message_received",
            subject=msg.subject,
            transport="nats",
        )
        try:
            payload = json.loads(msg.data.decode())
            text: str = payload["text"]
            user_id: str = payload["user_id"]
            vector_store_ids: list[str] = list(payload.get("vector_store_ids") or [])
            alpha_raw = payload.get("alpha")
            hybrid_alpha: float | None = float(alpha_raw) if alpha_raw is not None else None

            response = await invoke_graph(
                self._graph,
                self._memory,
                user_id,
                text,
                retriever=self._rag.retriever if vector_store_ids else None,
                vector_store_ids=vector_store_ids if vector_store_ids else None,
                hybrid_alpha=hybrid_alpha,
            )
            latency_ms = int((time.monotonic() - start) * 1000)

            result = json.dumps({"response": response}).encode()
            _log.info(
                "rag.chat.done",
                user_id=user_id,
                vs_count=len(vector_store_ids),
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            _log.error(
                f"rag nats chat error: {type(exc).__name__}",
                event_type="exception",
                error=str(exc),
                transport="nats",
                latency_ms=latency_ms,
            )
            result = json.dumps({"error": str(exc)}).encode()

        await self._publish(msg.reply, _SUBJECT_CHAT_RES, result)

    def is_connected(self) -> bool:
        """Return True if the NATS connection is active."""
        if not self._settings.nats_enabled:
            return True
        return self._nc is not None and self._nc.is_connected

    async def close(self) -> None:
        """Drain and close the NATS connection."""
        if self._nc is not None:
            await self._nc.drain()
            await self._nc.close()
            self._nc = None
