"""Boot the real DeepAgentTUI (bootstrap stubbed by the autouse fixture in
conftest) and assert the layout mounts and the connect-failure path degrades
gracefully. This is the integration net for refactors that move widgets around.
"""

from __future__ import annotations

import pytest
from textual.containers import Container, VerticalScroll
from textual.widgets import OptionList

from deepagent_tui import bootstrap as bootstrap_module
from deepagent_tui.tui.app import (
    ChatBar,
    ChatTextArea,
    DeepAgentTUI,
    StatusBar,
    WelcomeBanner,
)


async def test_app_boots_and_mounts_core_widgets() -> None:
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one(WelcomeBanner)
        app.query_one(ChatBar)
        app.query_one(ChatTextArea)
        app.query_one(StatusBar)
        app.query_one("#messages", Container)
        app.query_one("#main", VerticalScroll)
        app.query_one("#autocomplete", OptionList)


async def test_autocomplete_hidden_initially() -> None:
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        ac = app.query_one("#autocomplete", OptionList)
        assert "-hidden" in ac.classes


async def test_status_bar_refresh_uses_session_state() -> None:
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.session.input_tokens = 12
        app.session.output_tokens = 34
        sb = app.query_one(StatusBar)
        sb._refresh()  # would raise if any rendering helper broke
        assert "12" in str(sb.content)


async def test_connect_failure_does_not_crash_app(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _failing_connect(client, session) -> bool:
        return False

    monkeypatch.setattr(bootstrap_module, "connect", _failing_connect)
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        # The failure path schedules an exit; it must not crash the layout.
        app.query_one(ChatBar)
        app.query_one(StatusBar)
