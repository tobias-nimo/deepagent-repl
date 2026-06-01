"""Chat-bar input-history recall (up/down) and draft restore, plus the
file-reference rewriting and command-colouring of user messages.

The recall methods are driven directly — the key handler is a thin wrapper over
them and pilot key dispatch is flaky for unfocused-edge cases.
"""

from __future__ import annotations

from deepagent_tui.tui.app import (
    ChatTextArea,
    DeepAgentTUI,
    _command_color,
    _user_message_text,
)


async def test_input_history_recall_and_draft_restore() -> None:
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt", ChatTextArea)
        app._input_history = ["first message", "second message"]
        prompt.text = "draft in progress"

        # up → newest entry (stashing the draft), then the older one.
        assert app._history_recall_prev() is True
        assert prompt.text == "second message"
        assert app._history_recall_prev() is True
        assert prompt.text == "first message"
        # up at the oldest entry is swallowed without moving.
        assert app._history_recall_prev() is True
        assert prompt.text == "first message"

        # down steps back toward newer, then restores the draft and exits.
        assert app._history_recall_next() is True
        assert prompt.text == "second message"
        assert app._history_recall_next() is True
        assert prompt.text == "draft in progress"
        assert app._history_index is None
        # down with no active navigation lets the arrow move the cursor.
        assert app._history_recall_next() is False


async def test_input_history_recall_empty_is_noop() -> None:
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt", ChatTextArea)
        prompt.text = "typed"
        # No history yet → up does nothing and lets the cursor move.
        assert app._history_recall_prev() is False
        assert prompt.text == "typed"


async def test_resolve_file_refs_rewrites_existing(tmp_path) -> None:
    books = tmp_path / "books"
    books.mkdir()
    (books / "blah.md").write_text("hi")
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.session.workspace_root = str(tmp_path)
        display, agent = app._resolve_file_refs("read @books/blah.md please")
        assert display == "read @blah.md please"
        assert agent == f"read [blah.md]({books / 'blah.md'}) please"


async def test_resolve_file_refs_leaves_unknown(tmp_path) -> None:
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.session.workspace_root = str(tmp_path)
        # A casual @-mention that isn't a real file stays verbatim.
        display, agent = app._resolve_file_refs("ping @john now")
        assert display == "ping @john now"
        assert agent == "ping @john now"


def _colored_text(t, color: str) -> str:
    """Concatenate the characters of `t` that carry `color` in their span."""
    return "".join(t.plain[s.start : s.end] for s in t.spans if color in str(s.style))


def test_shell_message_renders_fully_in_command_color() -> None:
    t = _user_message_text("!ls -la /tmp")
    assert "!ls -la /tmp" in _colored_text(t, _command_color())


def test_file_ref_token_renders_in_command_color() -> None:
    t = _user_message_text("look at @src/main.py please")
    colored = _colored_text(t, _command_color())
    assert "@src/main.py" in colored
    assert "please" not in colored
