"""Autocomplete behaviour for the `/`, `@`, and email cases.

These drive `_refresh_autocomplete` / `_apply_file_completion` directly rather
than simulating keystrokes — the TextArea.Changed event takes an extra event-
loop tick to land and pilot key dispatch has been flaky for that across Textual
versions, so direct calls are deterministic.
"""

from __future__ import annotations

from textual.widgets import OptionList

from deepagent_tui.tui.app import ChatTextArea, DeepAgentTUI


async def test_slash_prefix_reveals_autocomplete() -> None:
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._refresh_autocomplete("/")
        ac = app.query_one("#autocomplete", OptionList)
        assert "-hidden" not in ac.classes
        assert ac.option_count > 0


async def test_at_prefix_reveals_file_list(tmp_path) -> None:
    (tmp_path / "alpha.txt").write_text("x")
    (tmp_path / "beta.txt").write_text("y")
    (tmp_path / "subdir").mkdir()
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.session.workspace_root = str(tmp_path)
        prompt = app.query_one("#prompt", ChatTextArea)
        prompt.text = "look at @a"
        prompt.move_cursor(prompt.document.end)
        app._refresh_autocomplete(prompt.text)
        ac = app.query_one("#autocomplete", OptionList)
        assert "-hidden" not in ac.classes
        assert app._ac_mode == "file"
        ids = {ac.get_option_at_index(i).id for i in range(ac.option_count)}
        assert "alpha.txt" in ids


async def test_at_before_workspace_known_shows_hint() -> None:
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.session.workspace_root = None  # no message sent yet
        prompt = app.query_one("#prompt", ChatTextArea)
        prompt.text = "see @"
        prompt.move_cursor(prompt.document.end)
        app._refresh_autocomplete(prompt.text)
        ac = app.query_one("#autocomplete", OptionList)
        assert "-hidden" not in ac.classes
        assert ac.option_count == 1
        # The hint row carries no id, so Tab / click does nothing.
        assert ac.get_option_at_index(0).id is None


async def test_at_completion_after_message_hints_at_middleware() -> None:
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.session.workspace_root = None
        app.session.messages = [{"role": "user", "content": "hi"}]
        prompt = app.query_one("#prompt", ChatTextArea)
        prompt.text = "see @"
        prompt.move_cursor(prompt.document.end)
        app._refresh_autocomplete(prompt.text)
        ac = app.query_one("#autocomplete", OptionList)
        assert "-hidden" not in ac.classes
        assert ac.option_count == 1
        label = str(ac.get_option_at_index(0).prompt)
        assert "Send a message first" not in label
        assert "docs/server-middleware.md" in label


async def test_at_completion_replaces_token(tmp_path) -> None:
    (tmp_path / "alpha.txt").write_text("x")
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.session.workspace_root = str(tmp_path)
        prompt = app.query_one("#prompt", ChatTextArea)
        prompt.text = "look at @a"
        prompt.move_cursor(prompt.document.end)
        app._refresh_autocomplete(prompt.text)
        app._apply_file_completion("alpha.txt")
        assert prompt.text == "look at @alpha.txt "
        assert app._ac_mode == "none"


async def test_email_does_not_trigger_file_list(tmp_path) -> None:
    (tmp_path / "alpha.txt").write_text("x")
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.session.workspace_root = str(tmp_path)
        prompt = app.query_one("#prompt", ChatTextArea)
        prompt.text = "mail me@example"
        prompt.move_cursor(prompt.document.end)
        app._refresh_autocomplete(prompt.text)
        ac = app.query_one("#autocomplete", OptionList)
        assert "-hidden" in ac.classes
        assert app._ac_mode == "none"
