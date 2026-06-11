"""Tests for the NL chat loop (Agent B), independent of Agents A/C real services.

A fake Anthropic client scripts a two-round tool-use conversation:
  round 1: stream text, then return a `tool_use` stop with a UI directive
           (`color_selection`) AND a backend action (`submit_fold`);
  round 2: stream text, then `end_turn`.

The service functions the handlers call are monkeypatched to return canned objects, so the
loop is exercised end-to-end without Agents A/C. Assertions: a `text` event was emitted, a
`directive` event matching `directive_from_tool`, a `job` event from the fold, and a final
`done`.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from app.nl import loop as loop_module
from app.nl.tools import directive_from_tool
from app.schemas import ChatRequest, SSEEvent


# --------------------------------------------------------------- fake Anthropic client
class _FakeToolUseBlock:
    type = "tool_use"

    def __init__(self, block_id: str, name: str, tool_input: dict):
        self.id = block_id
        self.name = name
        self.input = tool_input  # SDK delivers a parsed dict


class _FakeTextBlock:
    type = "text"

    def __init__(self, text: str):
        self.text = text


class _FakeFinalMessage:
    def __init__(self, content: list, stop_reason: str):
        self.content = content
        self.stop_reason = stop_reason


class _FakeStream:
    """Sync context manager mirroring anthropic's MessageStream surface."""

    def __init__(self, text_chunks: list[str], final: _FakeFinalMessage):
        self.text_stream = iter(text_chunks)
        self._final = final

    def __enter__(self) -> _FakeStream:
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def get_final_message(self) -> _FakeFinalMessage:
        return self._final


class _FakeMessages:
    def __init__(self, scripted: list[tuple[list[str], _FakeFinalMessage]]):
        self._scripted = scripted
        self.calls = 0

    def stream(self, **_kwargs) -> _FakeStream:
        text_chunks, final = self._scripted[self.calls]
        self.calls += 1
        return _FakeStream(text_chunks, final)


class _FakeClient:
    def __init__(self, scripted):
        self.messages = _FakeMessages(scripted)


# --------------------------------------------------------------- helpers
COLOR_INPUT = {"chain": "A", "residue_range": [40, 55], "color": "#e11d48"}
FOLD_INPUT = {"project_id": 1, "sequence_id": 7, "model": "boltz_2"}


def _build_scripted_client() -> _FakeClient:
    round1 = (
        ["Coloring the loop and submitting a fold. "],
        _FakeFinalMessage(
            content=[
                _FakeTextBlock("Coloring the loop and submitting a fold. "),
                _FakeToolUseBlock("toolu_color", "color_selection", COLOR_INPUT),
                _FakeToolUseBlock("toolu_fold", "submit_fold", FOLD_INPUT),
            ],
            stop_reason="tool_use",
        ),
    )
    round2 = (
        ["Done — job submitted and region highlighted."],
        _FakeFinalMessage(
            content=[_FakeTextBlock("Done — job submitted and region highlighted.")],
            stop_reason="end_turn",
        ),
    )
    return _FakeClient([round1, round2])


async def _drain(session, req, client) -> list[dict]:
    events: list[dict] = []
    async for ev in loop_module.run_chat(session, req, client=client):
        events.append(ev)
    return events


# --------------------------------------------------------------- tests
async def test_chat_loop_emits_text_directive_job_done(monkeypatch):
    # Stub the backend service called by submit_fold so we don't need Agent A's impl.
    fake_job = SimpleNamespace(
        id=42, provider_job_id="prov-xyz", state="queued", label="fold"
    )

    def fake_submit_fold(session, req):
        # Frozen signature: jobs.submit_fold(session, FoldSubmitRequest) -> FoldJob
        assert req.project_id == 1
        assert req.sequence_id == 7
        return fake_job

    monkeypatch.setattr("app.services.jobs.submit_fold", fake_submit_fold)

    client = _build_scripted_client()
    req = ChatRequest(project_id=1, message="Color residues 40-55 of chain A and fold seq 7")

    events = await _drain(session=None, req=req, client=client)

    kinds = [e["event"] for e in events]

    # A text delta was streamed.
    assert SSEEvent.text.value in kinds
    text_payloads = [
        json.loads(e["data"]) for e in events if e["event"] == SSEEvent.text.value
    ]
    assert any(p.get("delta") for p in text_payloads)

    # A directive event matching directive_from_tool's canonical conversion.
    directive_events = [
        json.loads(e["data"]) for e in events if e["event"] == SSEEvent.directive.value
    ]
    assert len(directive_events) == 1
    expected = directive_from_tool("color_selection", COLOR_INPUT)
    assert directive_events[0] == expected
    assert directive_events[0]["kind"] == "color"
    assert directive_events[0]["color"] == "#e11d48"
    assert directive_events[0]["target"]["chain"] == "A"
    assert directive_events[0]["target"]["residue_range"] == [40, 55]

    # A job event from the fold submission.
    job_events = [
        json.loads(e["data"]) for e in events if e["event"] == SSEEvent.job.value
    ]
    assert len(job_events) == 1
    assert job_events[0]["job_id"] == 42
    assert job_events[0]["provider_job_id"] == "prov-xyz"
    assert job_events[0]["state"] == "queued"

    # Exactly one terminal done with the model's stop reason.
    done_events = [
        json.loads(e["data"]) for e in events if e["event"] == SSEEvent.done.value
    ]
    assert len(done_events) == 1
    assert done_events[0]["stop_reason"] == "end_turn"

    # The loop ran two rounds (tool_use -> end_turn).
    assert client.messages.calls == 2


async def test_chat_loop_missing_api_key_emits_error_then_done(monkeypatch):
    # No injected client + missing key -> single error event, then done. No raise.
    def boom():
        from app.nl.client import MissingAPIKeyError

        raise MissingAPIKeyError("ANTHROPIC_API_KEY is required for the chat endpoint.")

    monkeypatch.setattr(loop_module, "get_anthropic_client", boom)

    req = ChatRequest(project_id=1, message="hello")
    events = await _drain(session=None, req=req, client=None)

    kinds = [e["event"] for e in events]
    assert kinds == [SSEEvent.error.value, SSEEvent.done.value]
    err = json.loads(events[0]["data"])
    assert "ANTHROPIC_API_KEY" in err["message"]


async def test_directive_tool_result_recovers_on_validation_error(monkeypatch):
    # A malformed directive (target.residues must be a list[int], here a string) must not
    # crash the loop: schemas.Directive(**payload) raises, dispatch_tool returns an error
    # tool_result, the loop feeds it back, and the conversation still completes.
    bad_color_block = _FakeToolUseBlock(
        "toolu_bad", "color_selection", {"residues": "oops-not-a-list", "color": "#fff"}
    )
    round1 = (
        [""],
        _FakeFinalMessage(content=[bad_color_block], stop_reason="tool_use"),
    )
    round2 = (
        ["Recovered."],
        _FakeFinalMessage(
            content=[_FakeTextBlock("Recovered.")], stop_reason="end_turn"
        ),
    )
    client = _FakeClient([round1, round2])

    req = ChatRequest(project_id=1, message="set representation")
    events = await _drain(session=None, req=req, client=client)

    kinds = [e["event"] for e in events]
    # No directive emitted (validation failed), but the loop completed cleanly.
    assert SSEEvent.directive.value not in kinds
    done_events = [
        json.loads(e["data"]) for e in events if e["event"] == SSEEvent.done.value
    ]
    assert len(done_events) == 1
    assert done_events[0]["stop_reason"] == "end_turn"
