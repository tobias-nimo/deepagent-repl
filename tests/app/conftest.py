"""Fixtures for the app-layer tests.

Every app test boots the real `DeepAgentTUI`, whose `on_mount` calls
`bootstrap.connect` and `bootstrap.discover_and_register_skills` — both touch
the network. The autouse fixture below replaces them with fakes that populate
`session.assistant_id` / `graph_id` / `thread_id` and report success, so the
whole app mounts without a LangGraph server.
"""

from __future__ import annotations

import pytest

from deepagent_tui import bootstrap as bootstrap_module


async def _fake_connect(client, session) -> bool:
    session.assistant_id = "test-assistant"
    session.graph_id = "test-graph"
    session.thread_id = "test-thread"
    return True


async def _fake_discover(client, session) -> None:
    return None


@pytest.fixture(autouse=True)
def stub_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the network-touching bootstrap helpers the TUI calls in on_mount."""
    monkeypatch.setattr(bootstrap_module, "connect", _fake_connect)
    monkeypatch.setattr(bootstrap_module, "discover_and_register_skills", _fake_discover)
