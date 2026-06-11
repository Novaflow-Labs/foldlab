"""Chat router: POST /chat -> text/event-stream (Anthropic agentic loop).

Streams the NL loop (nl.loop.run_chat) as Server-Sent Events. Event names follow
schemas.SSEEvent: text / directive / tool_result / job / done / error. `run_chat`
yields dicts already shaped for EventSourceResponse ({"event", "data"} with `data`
pre-encoded as a JSON string), so the route just forwards the async generator.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session
from sse_starlette.sse import EventSourceResponse

from ..db import get_session
from ..nl.loop import run_chat
from ..schemas import ChatRequest

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
async def chat(
    req: ChatRequest,
    session: Session = Depends(get_session),
) -> EventSourceResponse:
    return EventSourceResponse(run_chat(session, req))
