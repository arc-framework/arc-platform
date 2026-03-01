from __future__ import annotations

import logging
from typing import Annotated, Any, Optional

_log = logging.getLogger(__name__)

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from sherlock.memory import SherlockMemory

MAX_RETRIES = 3


# ─── Typed exception ──────────────────────────────────────────────────────────

class GraphErrorResponse(Exception):
    """Raised by invoke_graph when error_handler exhausted retries.

    This represents a graceful application-level failure — the graph completed
    successfully but could not produce a valid response. Callers (Pulsar, NATS)
    should ACK the message (do not redeliver) and publish the error to the caller.
    This is distinct from Path B (unhandled exception) where the message should NACK.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.error_message = message


# ─── Graph State ──────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    context: Optional[list[str]]
    final_response: Optional[str]
    error_count: int
    is_error: bool   # True when error_handler exhausted retries (Path A)


# ─── Node Factories ───────────────────────────────────────────────────────────

def _make_retrieve_context(memory: SherlockMemory) -> Any:
    async def retrieve_context(state: AgentState) -> dict[str, Any]:
        try:
            last = state["messages"][-1]
            query = last.content if isinstance(last.content, str) else ""
            context = await memory.search(state["user_id"], query)
            return {"context": context}
        except Exception:
            # Signal routing to error_handler via error_count increment
            return {"context": [], "error_count": state.get("error_count", 0) + 1}

    return retrieve_context


def _make_generate_response(llm: Any) -> Any:
    async def generate_response(state: AgentState) -> dict[str, Any]:
        context_chunks = state.get("context") or []
        context_text = "\n".join(context_chunks) if context_chunks else "No prior context."

        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(
                    content=(
                        "You are Sherlock, an analytical reasoning assistant. "
                        "Use the following conversation context to inform your reply.\n\n"
                        f"Context:\n{context_text}"
                    )
                ),
                *state["messages"],
            ]
        )
        chain = prompt | llm
        response = await chain.ainvoke({})
        text = response.content if hasattr(response, "content") else str(response)
        return {
            "messages": [AIMessage(content=text)],
            "final_response": text,
            "error_count": 0,
            "is_error": False,
        }

    return generate_response


def _make_error_handler(llm: Any) -> Any:
    async def error_handler(state: AgentState) -> dict[str, Any]:
        error_count = state.get("error_count", 0) + 1
        if error_count < MAX_RETRIES:
            # Retry dispatched by _route_after_error_handler
            return {"error_count": error_count, "is_error": False}
        # Retries exhausted — set is_error=True to signal Path A to invoke_graph
        error_msg = (
            f"I'm unable to process your request at the moment "
            f"(retried {MAX_RETRIES} times). Please try again later."
        )
        return {
            "messages": [AIMessage(content=error_msg)],
            "final_response": error_msg,
            "error_count": error_count,
            "is_error": True,
        }

    return error_handler


# ─── Routers ──────────────────────────────────────────────────────────────────

def _route_after_retrieve(state: AgentState) -> str:
    """Route to error_handler if retrieve_context raised; otherwise generate_response."""
    if state.get("error_count", 0) > 0:
        return "error_handler"
    return "generate_response"


def _route_after_generate(state: AgentState) -> str:
    """Route to END on success; to error_handler if final_response not set."""
    if state.get("final_response") is not None:
        return END
    return "error_handler"


def _route_after_error_handler(state: AgentState) -> str:
    """Retry generate_response if retries remain; otherwise END."""
    if state.get("error_count", 0) < MAX_RETRIES and state.get("final_response") is None:
        return "generate_response"
    return END


# ─── Graph Builder ────────────────────────────────────────────────────────────

def build_graph(memory: SherlockMemory, llm: Any) -> Any:
    """Build and compile the LangGraph 1.0.x state machine."""
    workflow: StateGraph = StateGraph(AgentState)

    workflow.add_node("retrieve_context", _make_retrieve_context(memory))
    workflow.add_node("generate_response", _make_generate_response(llm))
    workflow.add_node("error_handler", _make_error_handler(llm))

    workflow.add_edge(START, "retrieve_context")

    # retrieve_context: success → generate_response, exception → error_handler
    workflow.add_conditional_edges("retrieve_context", _route_after_retrieve)

    # generate_response: success → END, failed → error_handler
    workflow.add_conditional_edges("generate_response", _route_after_generate)

    # error_handler: retry → generate_response, exhausted → END
    workflow.add_conditional_edges("error_handler", _route_after_error_handler)

    return workflow.compile()


# ─── Public Invoke Helper ─────────────────────────────────────────────────────

async def invoke_graph(
    graph: Any,
    memory: SherlockMemory,
    user_id: str,
    text: str,
) -> str:
    """Run the compiled graph and persist both turns. Returns response string.

    Raises:
        GraphErrorResponse: when error_handler exhausted retries (graceful failure).
            Callers should ACK the message and publish the error — do NOT redeliver.
        RuntimeError: when an unhandled exception escapes the graph entirely.
            Callers should NACK / redeliver (Path B).
    """
    initial_state: AgentState = {
        "messages": [HumanMessage(content=text)],
        "user_id": user_id,
        "context": None,
        "final_response": None,
        "error_count": 0,
        "is_error": False,
    }

    try:
        final_state = await graph.ainvoke(initial_state)
    except Exception as exc:
        raise RuntimeError(f"Graph invocation failed: {exc}") from exc

    response: str = final_state.get("final_response") or "No response generated."

    # Persist both turns — best-effort, don't fail the response if storage is down
    try:
        await memory.save(user_id, "human", text)
        await memory.save(user_id, "ai", response)
    except Exception as exc:
        _log.warning("memory_save_failed", error=str(exc))

    # Path A: error_handler exhausted retries — raise typed exception so callers can
    # publish with "error" key and still ACK (do not redeliver — message was processed)
    if final_state.get("is_error", False):
        raise GraphErrorResponse(response)

    return response
