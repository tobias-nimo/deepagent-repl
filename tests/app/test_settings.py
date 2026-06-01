"""The settings screen: tab cycling, config-toggle persistence (round-tripping
through the per-agent config layer), and the panel leaving the chat visible
above it.
"""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from deepagent_tui.session import Session
from deepagent_tui.storage import config_store
from deepagent_tui.tui.app import DeepAgentTUI
from deepagent_tui.tui.screens import SettingsScreen


async def test_settings_screen_mounts_and_switches_tabs() -> None:
    """`_next_tab` / `_prev_tab` cycle the tab state machine. We call the screen
    methods directly because Pilot's key dispatch doesn't reliably route through
    Screen.on_key when no widget is focused — the logic under test is the
    cycling, not Textual's event plumbing."""
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = SettingsScreen(app.session)
        await app.push_screen(screen)
        await pilot.pause()

        assert screen._active_tab == 0
        assert screen.TABS == ("Config", "Harness", "Usage", "Status")
        for expected in (1, 2, 3, 0):  # forward cycle wraps
            screen._next_tab()
            assert screen._active_tab == expected
        screen._prev_tab()
        assert screen._active_tab == 3  # wraps backwards


async def test_config_toggle_persists(cfg_paths) -> None:
    """`_cycle_current` flips session state and round-trips through the on-disk
    config file. The `cfg_paths` fixture redirects config.toml to a tmp dir."""
    from deepagent_tui.ui import markdown as md
    from deepagent_tui.ui import tool_widgets as tw

    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        initial_hitl = app.session.hitl_enabled
        screen = SettingsScreen(app.session)
        await app.push_screen(screen)
        await pilot.pause()

        # Highlight defaults to row 0 (Tool widgets).
        assert screen._selected_row == 0

        # Auto-approve tools lives on row 1 — toggling flips hitl_enabled and
        # round-trips through this graph's override layer (not the default).
        screen._selected_row = 1
        screen._cycle_current(+1)
        assert app.session.hitl_enabled != initial_hitl
        loaded = config_store.load_config(app.session.graph_id)
        assert loaded.hitl_enabled == app.session.hitl_enabled

        # Tool widgets (row 0) writes the new mode and propagates to the
        # module-level flag the renderers read.
        screen._selected_row = 0
        before_mode = app.session.tool_widget_mode
        screen._cycle_current(+1)
        assert app.session.tool_widget_mode != before_mode
        assert tw._WIDGET_MODE == app.session.tool_widget_mode
        assert (
            config_store.load_config(app.session.graph_id).tool_widget_mode
            == app.session.tool_widget_mode
        )

        # Code snippets style (row 3) writes a valid Pygments style, propagates
        # to the markdown module, and round-trips to disk.
        screen._selected_row = 3
        before_theme = app.session.code_theme
        screen._cycle_current(+1)
        assert app.session.code_theme != before_theme
        assert app.session.code_theme in config_store._VALID_CODE_THEMES
        assert md._code_theme == app.session.code_theme
        assert (
            config_store.load_config(app.session.graph_id).code_theme
            == app.session.code_theme
        )


class _Stub(App):
    # Reproduce the production cascade: a bare `Screen` rule plus the
    # SettingsScreen override that the real App CSS adds.
    CSS = """
    Screen { background: $background; }
    SettingsScreen { background: $surface 70%; }
    #chat-top { dock: top; height: 5; background: red; color: white;
                content-align: center middle; }
    #chat-mid { background: blue; color: white; content-align: center middle; height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        yield Static("CHATBANNER", id="chat-top")
        yield Static("MIDDLE", id="chat-mid")


@pytest.mark.asyncio
async def test_chat_visible_above_panel():
    """SettingsScreen leaves the underlying screen visible above the panel."""
    app = _Stub()
    async with app.run_test(size=(40, 30)) as pilot:
        session = Session()
        session.hitl_enabled = True
        session.tool_widget_mode = "default"
        await app.push_screen(SettingsScreen(session))
        await pilot.pause()

        # Top ~30% should still show the underlying screen content.
        strips = app.screen._compositor.render_strips(app.size)
        top = "\n".join("".join(s.text for s in strip) for strip in strips[:9])
        assert "CHATBANNER" in top, f"chat banner not visible above panel:\n{top}"
