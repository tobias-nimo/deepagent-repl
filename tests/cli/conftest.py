"""Fixtures for the headless-CLI tests.

These exercise `cli/runner.py` with a stubbed `connect` and a fake stream/client
so no LangGraph server is required. `_FakeClient.events` / `.state` are set
per-test to script the stream and the post-run thread state.
"""

from __future__ import annotations

import types

import pytest

from deepagent_tui.cli import runner


async def _agen(events):
    for ev, data in events:
        yield types.SimpleNamespace(event=ev, data=data)


class FakeClient:
    """Stand-in for AgentClient. `events`/`state` are class attributes set per test."""

    events: list = []
    state: dict = {}

    def __init__(self, *args, **kwargs) -> None:
        pass

    def stream_message(self, thread_id, assistant_id, content):
        return _agen(self.events)

    def resume(self, thread_id, assistant_id, value):
        return _agen([])

    async def get_thread_state(self, thread_id):
        return self.state

    async def get_thread(self, thread_id):
        return {"thread_id": thread_id}


async def _fake_connect(client, session) -> bool:
    session.assistant_id = "test-assistant"
    session.graph_id = "test-graph"
    session.thread_id = "thread-123"
    return True


@pytest.fixture
def fake_client():
    """Expose the FakeClient class so tests can set `.events` / `.state`."""
    return FakeClient


@pytest.fixture
def stub(monkeypatch: pytest.MonkeyPatch):
    """Replace network/DB touchpoints the runner imports. Returns FakeClient so a
    test can script `FakeClient.events` / `FakeClient.state`."""
    monkeypatch.setattr(runner, "connect", _fake_connect)
    monkeypatch.setattr(runner, "AgentClient", FakeClient)

    async def _noop_upsert(*args, **kwargs) -> None:
        return None

    async def _no_record(thread_id):
        return None

    async def _no_threads(limit=200):
        return []

    monkeypatch.setattr(runner, "upsert_thread", _noop_upsert)
    monkeypatch.setattr(runner, "get_thread", _no_record)
    monkeypatch.setattr(runner, "list_threads", _no_threads)
    return FakeClient
