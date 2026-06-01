"""Smoke tests for the headless `deepagent` CLI run engine (`cli/runner.py`).

They assert the contract callers depend on: a one-shot prints the answer +
resume hint, JSON mode emits a clean structured object, a non-tool interrupt
aborts with exit code 2, resume without a message errors, and `list` renders
rows. The fake client/stream lives in `conftest.py`.
"""

from __future__ import annotations

import json

import pytest

from deepagent_tui.cli import runner


def _ai_update(content: str, tool_calls: list | None = None) -> tuple[str, dict]:
    msg = {"type": "ai", "content": content}
    if tool_calls is not None:
        msg["tool_calls"] = tool_calls
    return ("updates", {"agent": {"messages": [msg]}})


async def test_query_streams_answer_and_resume_hint(stub, capsys) -> None:
    stub.events = [_ai_update("Hello from the agent.")]
    stub.state = {}

    code = await runner.run_query("hi", "live")

    assert code == 0
    captured = capsys.readouterr()
    assert "Hello from the agent." in captured.out
    assert "Resume: deepagent resume thread-123" in captured.err


async def test_query_json_mode_emits_structured_object(stub, capsys) -> None:
    stub.events = [
        _ai_update(
            "Answer.",
            tool_calls=[{"id": "t1", "name": "read_file", "args": {"path": "README.md"}}],
        )
    ]
    stub.state = {}

    code = await runner.run_query("hi", "json")

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["thread_id"] == "thread-123"
    assert payload["response"] == "Answer."
    assert payload["tool_calls"] == ["read_file(path=README.md)"]
    assert payload["interrupted"] is False
    assert payload["resume_command"].startswith("deepagent resume thread-123")


async def test_query_aborts_on_non_tool_interrupt(stub, capsys) -> None:
    stub.events = [_ai_update("Let me check.")]
    stub.state = {
        "interrupts": [
            {"id": "i1", "value": {"question": "Which env?", "options": ["staging", "prod"]}}
        ]
    }

    code = await runner.run_query("deploy", "live")

    assert code == 2
    err = capsys.readouterr().err
    assert "Agent needs input" in err
    assert "Which env?" in err
    assert "staging, prod" in err


async def test_resume_requires_message_when_not_interrupted(stub, capsys) -> None:
    stub.events = []
    stub.state = {}

    code = await runner.run_resume("thread-123", None, "live")

    assert code == 1
    assert "message is required" in capsys.readouterr().err


async def test_run_list_prints_threads(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    async def _fake_list(limit=50, *, graph_id=None, workspace=None):
        return [
            {
                "id": "abcd1234ef",
                "updated_at": "2026-05-28 10:00:00",
                "graph_id": "jarvis",
                "message_count": 3,
                "last_message": "hi there",
            }
        ]

    monkeypatch.setattr(runner, "list_threads", _fake_list)

    code = await runner.run_list()

    assert code == 0
    out = capsys.readouterr().out
    assert "abcd1234" in out
    assert "hi there" in out
