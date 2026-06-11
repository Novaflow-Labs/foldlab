"""Agentic chat loop -> SSE event generator.

`run_chat` is an async generator yielding SSE event dicts shaped for sse-starlette's
`EventSourceResponse`: ``{"event": <name>, "data": <json string>}``. It:

  1. Builds the initial messages (viewer context prepended as a <system-reminder> note).
  2. Streams the model's text deltas as `text` events.
  3. Runs the Anthropic tool-use loop (capped at MAX_ITERATIONS): for each `tool_use`
     block it dispatches the tool, forwards the handler's `directive` / `job` SSE events,
     and feeds a `tool_result` back to the model.
  4. Emits `done` on completion, or `error` + `done` on failure / missing API key.

The Anthropic SDK's `messages.stream(...)` is a *synchronous*, blocking context manager.
To keep deltas flowing without blocking the event loop, the blocking loop runs in a worker
thread (`anyio.to_thread.run_sync`) and pushes events into an `anyio` memory object stream
that this async generator drains. Tool dispatch is async (it calls sync services via threads);
the worker thread runs it back on the event loop with `anyio.from_thread.run`, and uses
`anyio.from_thread.run_sync` for the sync stream sends/close.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import anyio
from sqlmodel import Session

from ..config import get_settings
from ..schemas import ChatRequest, SSEEvent
from .client import MissingAPIKeyError, get_anthropic_client
from .handlers import dispatch_tool
from .prompt import SYSTEM
from .tools import ALL_TOOLS

MAX_ITERATIONS = 8
MAX_TOKENS = 4096

# System sent as a single cached text block; ALL_TOOLS (frozen order) renders before it,
# so tools + system cache together. SYSTEM is static (no timestamps) — cache stays warm.
SYSTEM_BLOCKS = [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}]


def _build_initial_messages(req: ChatRequest) -> list[dict[str, Any]]:
    """One user message: viewer context as a <system-reminder> note, then the user text."""
    parts: list[str] = []
    if req.context:
        ctx = json.dumps(req.context, sort_keys=True, default=str)
        parts.append(
            "<system-reminder>\nCurrent viewer context (use it to resolve references like "
            f'"this" / "the selected residue"):\n{ctx}\n</system-reminder>'
        )
    parts.append(req.message)
    return [{"role": "user", "content": "\n\n".join(parts)}]


def _sse(event: SSEEvent, data: dict[str, Any]) -> dict[str, str]:
    """Shape an event for EventSourceResponse (data JSON-encoded as the wire format expects)."""
    return {"event": event.value, "data": json.dumps(data, default=str)}


async def run_chat(
    session: Session,
    req: ChatRequest,
    client: Any | None = None,
) -> AsyncIterator[dict[str, str]]:
    """Drive the chat loop, yielding SSE event dicts. Never raises out of the generator."""
    if client is None:
        try:
            client = get_anthropic_client()
        except MissingAPIKeyError as exc:
            yield _sse(SSEEvent.error, {"message": str(exc)})
            yield _sse(SSEEvent.done, {"stop_reason": "error"})
            return

    model = get_settings().anthropic_model
    messages = _build_initial_messages(req)

    # Worker thread pushes (kind, payload) tuples; this coroutine drains and yields them.
    # Buffer is generous and events are small, so a non-blocking send is safe here.
    send_stream, receive_stream = anyio.create_memory_object_stream[
        tuple[str, dict[str, Any]]
    ](max_buffer_size=1024)

    def _emit(kind: str, payload: dict[str, Any]) -> None:
        """Push one event onto the stream from the worker thread (sync send)."""
        anyio.from_thread.run_sync(send_stream.send_nowait, (kind, payload))

    def _run_blocking() -> None:
        """Runs in a worker thread: the full streaming + tool loop (blocking SDK calls)."""
        try:
            stop_reason = "end_turn"
            for _ in range(MAX_ITERATIONS):
                with client.messages.stream(
                    model=model,
                    max_tokens=MAX_TOKENS,
                    system=SYSTEM_BLOCKS,
                    tools=ALL_TOOLS,
                    thinking={"type": "adaptive"},
                    output_config={"effort": "high"},
                    messages=messages,
                ) as stream:
                    for text in stream.text_stream:
                        if text:
                            _emit("text", {"delta": text})
                    resp = stream.get_final_message()

                messages.append({"role": "assistant", "content": resp.content})
                stop_reason = resp.stop_reason or "end_turn"

                if stop_reason != "tool_use":
                    break

                tool_results: list[dict[str, Any]] = []
                for block in resp.content:
                    if getattr(block, "type", None) != "tool_use":
                        continue
                    # block.input is already a parsed dict from the SDK.
                    # dispatch_tool is async (calls sync services via threads); run it on the loop.
                    content_json, sse_events = anyio.from_thread.run(
                        dispatch_tool, session, req.project_id, block.name, block.input
                    )
                    for ev in sse_events:
                        _emit("sse", ev)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": content_json,
                        }
                    )

                if not tool_results:
                    break
                messages.append({"role": "user", "content": tool_results})

            _emit("done", {"stop_reason": stop_reason})
        except Exception as exc:  # noqa: BLE001 - report any failure as an SSE error
            _emit("error", {"message": f"{type(exc).__name__}: {exc}"})
            _emit("done", {"stop_reason": "error"})
        finally:
            anyio.from_thread.run_sync(send_stream.close)

    async with anyio.create_task_group() as tg:
        async def _worker() -> None:
            await anyio.to_thread.run_sync(_run_blocking)

        tg.start_soon(_worker)

        async with receive_stream:
            async for kind, payload in receive_stream:
                if kind == "text":
                    yield _sse(SSEEvent.text, payload)
                elif kind == "sse":
                    # Handler-produced event: {"event": <SSEEvent value>, "data": dict}.
                    yield {
                        "event": payload["event"],
                        "data": json.dumps(payload["data"], default=str),
                    }
                elif kind == "error":
                    yield _sse(SSEEvent.error, payload)
                elif kind == "done":
                    yield _sse(SSEEvent.done, payload)
