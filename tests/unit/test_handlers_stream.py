"""Text-streaming and update-parsing logic in handlers/stream.py.

`process_messages_event` must emit only the newly-added tail regardless of
whether the server frames partials as cumulative messages-so-far (type "ai") or
as token deltas (type "AIMessageChunk"). `process_updates_event` collects full
tool calls / results, accumulates usage, captures the model name, and resets the
tail tracker at each message boundary.
"""

from __future__ import annotations

from deepagent_tui.handlers.stream import (
    StreamState,
    extract_text_content,
    process_messages_event,
    process_updates_event,
)


def _partial(text: str, msg_type: str) -> list[dict]:
    return [{"type": msg_type, "content": text}]


# ── extract_text_content ──────────────────────────────────────────────────


def test_extract_text_content_handles_str_list_and_other():
    assert extract_text_content("plain") == "plain"
    blocks = [{"type": "text", "text": "a"}, {"type": "image", "x": 1}, "b"]
    # text blocks and bare strings are joined; non-text dict blocks are dropped.
    assert extract_text_content(blocks) == "a\nb"
    assert extract_text_content(42) == "42"


# ── streaming text deltas ─────────────────────────────────────────────────


def test_cumulative_partials_emit_only_the_tail():
    state = StreamState()
    frags = [
        process_messages_event(_partial("Hello", "ai"), state),
        process_messages_event(_partial("Hello world", "ai"), state),
        process_messages_event(_partial("Hello world!", "ai"), state),
    ]
    assert frags == ["Hello", " world", "!"]
    assert "".join(frags) == state.text_buffer


def test_token_delta_partials_are_appended():
    state = StreamState()
    frags = [
        process_messages_event(_partial("Hello", "AIMessageChunk"), state),
        process_messages_event(_partial(" world", "AIMessageChunk"), state),
        process_messages_event(_partial("!", "AIMessageChunk"), state),
    ]
    assert frags == ["Hello", " world", "!"]
    assert state.text_buffer == "Hello world!"


def test_no_new_text_returns_none():
    state = StreamState()
    process_messages_event(_partial("Hello", "ai"), state)
    # Same cumulative payload again — nothing new to emit.
    assert process_messages_event(_partial("Hello", "ai"), state) is None


def test_messages_event_collects_streaming_tool_call_chunks():
    state = StreamState()
    chunk = {
        "type": "AIMessageChunk",
        "content": "",
        "tool_call_chunks": [{"id": "c1", "name": "read_file", "args": ""}],
    }
    process_messages_event([chunk], state)
    # A second chunk with the same id must not double-register the call.
    process_messages_event([chunk], state)
    assert [tc["id"] for tc in state.tool_calls] == ["c1"]
    assert state.tool_calls[0]["name"] == "read_file"


def test_non_dict_chunks_are_skipped():
    state = StreamState()
    assert process_messages_event(["not-a-dict", 5], state) is None


# ── updates events ────────────────────────────────────────────────────────


def test_updates_boundary_resets_tail_tracker():
    """A second streamed message in the same run starts its cumulative partials
    from scratch; without a reset its first tail would re-include the whole
    message."""
    state = StreamState()
    process_messages_event(_partial("First message.", "ai"), state)

    process_updates_event(
        {"agent": {"messages": [{"type": "ai", "content": "First message."}]}},
        state,
    )
    assert state.text_buffer == ""

    f1 = process_messages_event(_partial("Second", "ai"), state)
    f2 = process_messages_event(_partial("Second message", "ai"), state)
    assert f1 == "Second"
    assert f2 == " message"


def test_updates_collects_tool_calls_results_usage_and_model():
    state = StreamState()
    data = {
        "agent": {
            "messages": [
                {
                    "type": "ai",
                    "content": "ok",
                    "tool_calls": [{"id": "tc1", "name": "bash", "args": {}}],
                    "usage_metadata": {"input_tokens": 100, "output_tokens": 20},
                    "response_metadata": {"model_name": "claude-opus-4-8"},
                },
                {"type": "tool", "tool_call_id": "tc1", "content": "done"},
            ]
        }
    }
    msgs = process_updates_event(data, state)
    assert len(msgs) == 2  # ai + tool both forwarded for rendering
    assert [tc["id"] for tc in state.tool_calls] == ["tc1"]
    assert len(state.tool_results) == 1
    assert state.total_input_tokens == 100
    assert state.total_output_tokens == 20
    assert state.last_input_tokens == 100
    assert state.model == "claude-opus-4-8"


def test_updates_ignores_non_dict_payload():
    state = StreamState()
    assert process_updates_event("nope", state) == []
